"""Composition root. Owner: M3 (C-05).

One place builds the engines, repositories, adapters and services, so a handler
receives collaborators instead of constructing them and a test can replace any
one of them. Nothing here is created per request.

The two engines are separate by construction: `career_app` and `career_jobs`
have different URLs and roles, and no object in this container can open a
transaction across both.
"""

from __future__ import annotations

from dataclasses import dataclass
from functools import cached_property

from app.core.clock import Clock, SystemClock
from app.core.inference import build_embedding_client
from app.core.settings import Settings
from app.core.storage import build_object_store
from app.db.app.analyses import SqlAnalysisRepository
from app.db.app.database import create_app_engine, session_factory
from app.db.app.explanations import SqlExplanationStore
from app.db.app.matches import SqlMatchRepository, SqlRecommendationRepository
from app.db.app.profiles import (
    SqlCandidateEmbeddingRepository,
    SqlProfileRepository,
    SqlResumeUploadRepository,
)
from app.db.app.queue import SqlAnalysisQueue, SqlMatchQueue
from app.db.app.sessions import SqlSessionStore
from app.db.jobs.database import create_job_engine
from app.db.jobs.database import session_factory as job_session_factory
from app.db.jobs.repository import SqlJobRepository
from app.modules.explanations.llm import build_llm_client
from app.modules.explanations.service import ExplanationService
from app.orchestration.job_events import MatchService, OutboxDispatcher
from app.orchestration.refresh import RecommendationPublisher
from app.orchestration.retention import RetentionCleaner
from app.orchestration.runs import SqlMatchRunRepository


@dataclass
class Container:
    settings: Settings
    clock: Clock = SystemClock()

    @cached_property
    def app_sessions(self):
        return session_factory(create_app_engine(self.settings))

    @cached_property
    def job_sessions(self):
        return job_session_factory(create_job_engine(self.settings))

    # --- career_app repositories -------------------------------------------------
    @cached_property
    def sessions(self) -> SqlSessionStore:
        return SqlSessionStore(self.app_sessions, self.clock, self.settings.profile_retention_days)

    @cached_property
    def profiles(self) -> SqlProfileRepository:
        return SqlProfileRepository(self.app_sessions, self.clock)

    @cached_property
    def uploads(self) -> SqlResumeUploadRepository:
        return SqlResumeUploadRepository(self.app_sessions, self.clock)

    @cached_property
    def candidate_embeddings(self) -> SqlCandidateEmbeddingRepository:
        return SqlCandidateEmbeddingRepository(self.app_sessions, self.clock)

    @cached_property
    def analyses(self) -> SqlAnalysisRepository:
        return SqlAnalysisRepository(self.app_sessions, self.clock)

    @cached_property
    def matches(self) -> SqlMatchRepository:
        return SqlMatchRepository(self.app_sessions)

    @cached_property
    def recommendations(self) -> SqlRecommendationRepository:
        return SqlRecommendationRepository(self.app_sessions, self.clock)

    @cached_property
    def explanation_store(self) -> SqlExplanationStore:
        return SqlExplanationStore(self.app_sessions, self.clock)

    @cached_property
    def runs(self) -> SqlMatchRunRepository:
        return SqlMatchRunRepository(self.app_sessions, self.clock)

    # --- career_jobs (M2 owns the implementation; M3 only wires it) --------------
    @cached_property
    def jobs(self) -> SqlJobRepository:
        return SqlJobRepository(self.job_sessions)

    # --- queues and adapters ------------------------------------------------------
    @cached_property
    def match_queue(self) -> SqlMatchQueue:
        return SqlMatchQueue(self.app_sessions, self.clock)

    @cached_property
    def analysis_queue(self) -> SqlAnalysisQueue:
        return SqlAnalysisQueue(self.app_sessions, self.clock)

    @cached_property
    def object_store(self):
        return build_object_store(self.settings)

    @cached_property
    def embedding_client(self):
        return build_embedding_client(self.settings)

    @cached_property
    def explanations(self) -> ExplanationService:
        return ExplanationService(
            self.explanation_store, build_llm_client(self.settings), self.clock
        )

    @cached_property
    def publisher(self) -> RecommendationPublisher:
        return RecommendationPublisher(self.profiles, self.jobs, self.matches, self.recommendations)

    @cached_property
    def retention(self) -> RetentionCleaner:
        return RetentionCleaner(self.app_sessions, self.object_store, self.clock)

    @cached_property
    def dispatcher(self) -> OutboxDispatcher:
        return OutboxDispatcher(self.jobs, self.match_queue)

    def match_service(self, matcher) -> MatchService:
        """M2 supplies the matcher; the worker entry point injects it."""
        return MatchService(
            self.profiles,
            self.jobs,
            self.matches,
            matcher,
            self.publisher,
            self.runs,
            self.clock,
            batch_size=self.settings.match_batch_size,
        )
