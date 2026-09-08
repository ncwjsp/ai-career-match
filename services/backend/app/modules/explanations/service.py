"""Explanation generation, validation and caching. Owner: M3 (C-02).

The order matters: the score, skill states, strengths and gaps already exist
before a word is generated. The model only writes prose about them, and its
output is validated against them before anyone sees it:

  - the reply must parse as the agreed JSON object;
  - every strength and gap must be one the application computed, so a model
    cannot invent a skill the resume never evidenced;
  - any percentage in the prose must equal the computed score, so prose cannot
    contradict the ranking;
  - the summary must be non-empty and bounded.

A failure at any step - provider outage, malformed reply, invented content -
produces the `unavailable` state, which still shows the real strengths, gaps and
evidence. A generation failure is never presented as a successful explanation,
and generated text never feeds back into a score.
"""

from __future__ import annotations

import json
import re
from datetime import datetime

from app.contracts.models import (
    CandidateProfile,
    JobPosting,
    MatchExplanation,
    Recommendation,
)
from app.core.clock import Clock
from app.core.errors import DependencyUnavailable
from app.db.app.explanations import SqlExplanationStore
from app.modules.explanations.context import ExplanationContext, build_context
from app.modules.explanations.llm import LlmClient
from app.modules.explanations.prompts import PROMPT_VERSION, render

MAX_SUMMARY_CHARS = 1200
PERCENTAGE = re.compile(r"(\d+(?:\.\d+)?)\s*%")


class InvalidGeneration(ValueError):
    """The reply did not survive validation against the computed evidence."""


class ExplanationService:
    def __init__(
        self,
        store: SqlExplanationStore,
        client: LlmClient,
        clock: Clock,
        prompt_version: str = PROMPT_VERSION,
    ):
        self._store = store
        self._client = client
        self._clock = clock
        self._prompt_version = prompt_version

    def cached(self, candidate_id: str, revision: int, job_id: str) -> MatchExplanation | None:
        return self._store.get(candidate_id, revision, job_id)

    def explain(
        self, profile: CandidateProfile, job: JobPosting, recommendation: Recommendation
    ) -> MatchExplanation:
        """Return a cached explanation, or generate, validate and cache a new one."""
        cached = self.cached(
            recommendation.candidate_id, recommendation.revision, recommendation.job_id
        )
        if cached is not None and cached.state == "ready":
            return cached

        context = build_context(profile, job, recommendation)
        now = self._clock.now()
        try:
            generation = self._client.generate(render(context))
            text = _validate(generation.text, context)
        except (DependencyUnavailable, InvalidGeneration):
            explanation = self._unavailable(recommendation, context, now)
        else:
            explanation = self._ready(recommendation, context, text, generation, now)
        self._store.put(explanation)
        return explanation

    def _ready(self, recommendation, context, text, generation, now) -> MatchExplanation:
        return _explanation(
            recommendation,
            context,
            state="ready",
            text=text,
            model_version=generation.model_version,
            prompt_version=self._prompt_version,
            generated_at=now,
        )

    def _unavailable(self, recommendation, context, now) -> MatchExplanation:
        # The state is honest about what failed; the evidence-backed strengths,
        # gaps and spans are still shown, because they never came from a model.
        return _explanation(
            recommendation,
            context,
            state="unavailable",
            text=None,
            model_version=None,
            prompt_version=self._prompt_version,
            generated_at=now,
        )


def _explanation(
    recommendation: Recommendation,
    context: ExplanationContext,
    *,
    state: str,
    text: str | None,
    model_version: str | None,
    prompt_version: str,
    generated_at: datetime,
) -> MatchExplanation:
    return MatchExplanation(
        candidate_id=recommendation.candidate_id,
        revision=recommendation.revision,
        profile_version=recommendation.profile_version,
        job_id=recommendation.job_id,
        job_version=recommendation.job_version,
        scoring_version=recommendation.scoring_version,
        state=state,
        text=text,
        strengths=list(context.strengths),
        gaps=list(context.gaps),
        evidence=list(recommendation.evidence),
        model_version=model_version,
        prompt_version=prompt_version,
        generated_at=generated_at if state == "ready" else None,
    )


def _validate(reply: str, context: ExplanationContext) -> str:
    try:
        parsed = json.loads(_strip_fences(reply))
    except json.JSONDecodeError as error:
        raise InvalidGeneration("The reply was not JSON.") from error
    if not isinstance(parsed, dict):
        raise InvalidGeneration("The reply was not a JSON object.")

    summary = parsed.get("summary")
    if not isinstance(summary, str) or not summary.strip():
        raise InvalidGeneration("The reply had no summary.")
    if len(summary) > MAX_SUMMARY_CHARS:
        raise InvalidGeneration("The summary exceeded the configured length.")

    for field, allowed in (("strengths", context.strengths), ("gaps", context.gaps)):
        values = parsed.get(field, [])
        if not isinstance(values, list) or not all(isinstance(v, str) for v in values):
            raise InvalidGeneration(f"{field} was not a list of strings.")
        invented = set(values) - set(allowed)
        if invented:
            raise InvalidGeneration(f"{field} contained content the application did not compute.")

    for value in PERCENTAGE.findall(summary):
        if abs(float(value) - context.score) > 0.05:
            raise InvalidGeneration("The summary stated a score the application did not compute.")
    return summary.strip()


def _strip_fences(reply: str) -> str:
    """Tolerate a ```json fence around an otherwise valid reply."""
    text = reply.strip()
    if text.startswith("```"):
        text = text.split("\n", 1)[-1]
        text = text.rsplit("```", 1)[0]
    return text.strip()
