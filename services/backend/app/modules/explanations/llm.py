"""Provider-neutral explanation generation. Owner: M3 (C-02).

`LlmClient` is the whole provider surface: one prompt in, one text out, with a
model identifier for the audit trail. Bedrock is the first real provider because
the 2026-09-08 revision brings an AWS account, but nothing above this module
knows that; swapping providers is a settings change plus one class.

Every failure - timeout, throttling, a refusal, an empty body - raises
`DependencyUnavailable`. The service above then presents the evidence-only
state. A generation failure is never dressed up as a successful explanation.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Protocol

from app.core.errors import DependencyUnavailable
from app.core.settings import Settings


@dataclass(frozen=True)
class Generation:
    text: str
    model_version: str


class LlmClient(Protocol):
    def generate(self, prompt: str) -> Generation: ...


class FakeLlmClient:
    """Deterministic offline generator used by tests and the default mock mode.

    It echoes the computed facts back in the required JSON shape. It performs no
    reasoning, and `Settings.validate_for_runtime` refuses it in real mode.
    """

    model_version = "fake-explainer-1"

    def generate(self, prompt: str) -> Generation:
        strengths = _bullets_after(prompt, "Strengths you may cite:")
        gaps = _bullets_after(prompt, "Gaps you may cite:")
        score = _score(prompt)
        summary = (
            f"This role matches at {score}. "
            + ("Strengths: " + ", ".join(strengths) + ". " if strengths else "")
            + ("Missing: " + ", ".join(gaps) + "." if gaps else "")
        ).strip()
        return Generation(
            text=json.dumps({"summary": summary, "strengths": strengths, "gaps": gaps}),
            model_version=self.model_version,
        )


def _bullets_after(prompt: str, heading: str) -> list[str]:
    if heading not in prompt:
        return []
    section = prompt.split(heading, 1)[1]
    items = []
    for raw in section.splitlines():
        line = raw.strip()
        if not line:
            if items:
                break
            continue  # The remainder of the heading line itself.
        if not line.startswith("- "):
            break
        value = line[2:]
        if value != "none recorded":
            items.append(value)
    return items


def _score(prompt: str) -> str:
    for line in prompt.splitlines():
        if line.startswith("Computed match score:"):
            return line.split(":", 1)[1].strip()
    return "an unknown score"


class BedrockLlmClient:
    """Amazon Bedrock adapter. `client` is injected so tests stay offline."""

    def __init__(self, model_id: str, client=None, region: str | None = None, timeout: int = 30):
        if not model_id:
            raise ValueError("BedrockLlmClient requires a model id.")
        self._model_id = model_id
        self._client = client
        self._region = region
        self._timeout = timeout

    @property
    def client(self):
        if self._client is None:
            self._client = _build_bedrock_client(self._region, self._timeout)
        return self._client

    def generate(self, prompt: str) -> Generation:
        try:
            response = self.client.converse(
                modelId=self._model_id,
                messages=[{"role": "user", "content": [{"text": prompt}]}],
                inferenceConfig={"maxTokens": 600, "temperature": 0.2},
            )
            blocks = response["output"]["message"]["content"]
            text = "".join(block.get("text", "") for block in blocks).strip()
        except Exception as error:  # noqa: BLE001 - any provider failure is an outage
            raise DependencyUnavailable("The explanation service is unavailable.") from error
        if not text:
            raise DependencyUnavailable("The explanation service returned no text.")
        return Generation(text=text, model_version=self._model_id)


def _build_bedrock_client(region: str | None, timeout: int):
    try:
        import boto3
        from botocore.config import Config
    except ModuleNotFoundError as error:  # pragma: no cover - boto3 is pinned
        raise DependencyUnavailable("boto3 is required for Bedrock generation.") from error
    return boto3.client(
        "bedrock-runtime",
        region_name=region,
        config=Config(read_timeout=timeout, connect_timeout=min(timeout, 10)),
    )


def build_llm_client(settings: Settings) -> LlmClient:
    if settings.llm_provider == "fake":
        return FakeLlmClient()
    return BedrockLlmClient(
        model_id=settings.llm_model_id,
        region=settings.aws_region,
        timeout=settings.llm_timeout_seconds,
    )
