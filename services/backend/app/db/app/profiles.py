"""Candidate profiles, upload metadata and resume vectors. Owner: M3 (C-01).

`SqlProfileRepository` implements `app.contracts.interfaces.ProfileRepository`.
Two rules shape it:

  - A profile version is immutable. Re-saving the same version with the same
    content is a no-op (a redelivered task), and re-saving it with different
    content is a conflict rather than a silent overwrite, because published
    recommendation revisions already cite that version.
  - `candidates.matching_enabled` / `candidates.expires_at` are the source of
    truth for retention, not the copy inside a stored payload. `get`/`list_active`
    return the DTO with those two fields taken from the candidate row, so
    disabling matching takes effect immediately for every stored version.
"""

from __future__ import annotations

from collections.abc import Sequence
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from app.contracts.models import CandidateProfile, EmbeddingRecord, FileRef
from app.core.clock import Clock
from app.core.errors import ConflictError, NotFound
from app.core.timeutil import from_storage_utc, to_storage_utc
from app.db.app.models import (
    CandidateEmbeddingRow,
    CandidateProfileRow,
    CandidateRow,
    ResumeUploadRow,
)


class ProfileVersionConflict(ConflictError):
    """Raised when a stored profile version is re-saved with different content."""


def _profile_payload(profile: CandidateProfile) -> dict:
    return profile.model_dump(mode="json")


class SqlProfileRepository:
    def __init__(self, factory: sessionmaker[Session], clock: Clock):
        self._factory = factory
        self._clock = clock

    def _to_contract(self, row: CandidateProfileRow, candidate: CandidateRow) -> CandidateProfile:
        payload = dict(row.payload)
        payload["matching_enabled"] = candidate.matching_enabled
        payload["expires_at"] = from_storage_utc(candidate.expires_at)
        return CandidateProfile.model_validate(payload)

    def get(self, candidate_id: str, version: int | None = None) -> CandidateProfile | None:
        with self._factory() as session:
            candidate = session.get(CandidateRow, candidate_id)
            if candidate is None:
                return None
            wanted = version if version is not None else candidate.current_profile_version
            if wanted is None:
                return None
            row = session.get(CandidateProfileRow, (candidate_id, wanted))
            return self._to_contract(row, candidate) if row is not None else None

    def save(self, profile: CandidateProfile) -> None:
        now = to_storage_utc(self._clock.now())
        payload = _profile_payload(profile)
        with self._factory() as session:
            candidate = session.get(CandidateRow, profile.candidate_id)
            if candidate is None:
                raise NotFound("A profile needs an existing candidate session.")
            existing = session.get(
                CandidateProfileRow, (profile.candidate_id, profile.profile_version)
            )
            if existing is not None:
                if _comparable(existing.payload) != _comparable(payload):
                    raise ProfileVersionConflict(
                        f"profile_version {profile.profile_version} already stores "
                        "different content."
                    )
            else:
                session.add(
                    CandidateProfileRow(
                        candidate_id=profile.candidate_id,
                        profile_version=profile.profile_version,
                        resume_id=profile.resume_id,
                        language=profile.language,
                        payload=payload,
                        created_at=now,
                    )
                )
            if (
                candidate.current_profile_version is None
                or profile.profile_version > candidate.current_profile_version
            ):
                candidate.current_profile_version = profile.profile_version
                candidate.updated_at = now
            session.commit()

    def list_active(
        self, at: datetime, limit: int = 100, after_id: str | None = None
    ) -> Sequence[CandidateProfile]:
        """One bounded batch of matchable candidates, ordered by id for checkpointing."""
        boundary = to_storage_utc(at)
        with self._factory() as session:
            query = (
                select(CandidateRow)
                .where(CandidateRow.matching_enabled.is_(True))
                .where(CandidateRow.expires_at > boundary)
                .where(CandidateRow.current_profile_version.is_not(None))
                .order_by(CandidateRow.candidate_id)
                .limit(limit)
            )
            if after_id is not None:
                query = query.where(CandidateRow.candidate_id > after_id)
            candidates = session.execute(query).scalars().all()
            profiles = []
            for candidate in candidates:
                row = session.get(
                    CandidateProfileRow,
                    (candidate.candidate_id, candidate.current_profile_version),
                )
                if row is not None:
                    profiles.append(self._to_contract(row, candidate))
            return profiles

    def set_matching_enabled(self, candidate_id: str, enabled: bool) -> None:
        """Stop or resume matching for a retained candidate without deleting data."""
        with self._factory() as session:
            candidate = session.get(CandidateRow, candidate_id)
            if candidate is None:
                raise NotFound("Unknown candidate.")
            candidate.matching_enabled = enabled
            candidate.updated_at = to_storage_utc(self._clock.now())
            session.commit()

    def is_active(self, candidate_id: str, at: datetime) -> bool:
        """Re-checked immediately before a match run commits."""
        with self._factory() as session:
            candidate = session.get(CandidateRow, candidate_id)
            if candidate is None:
                return False
            expires_at = from_storage_utc(candidate.expires_at)
            return bool(candidate.matching_enabled and expires_at > to_storage_utc(at))


def _comparable(payload: dict) -> dict:
    """Compare stored content without the two fields the candidate row owns."""
    return {k: v for k, v in payload.items() if k not in {"matching_enabled", "expires_at"}}


class SqlResumeUploadRepository:
    """Upload metadata only. The bytes live in the object store."""

    def __init__(self, factory: sessionmaker[Session], clock: Clock):
        self._factory = factory
        self._clock = clock

    def record(
        self,
        resume_id: str,
        candidate_id: str,
        file: FileRef,
        byte_size: int,
        original_filename: str | None = None,
    ) -> None:
        with self._factory() as session:
            session.add(
                ResumeUploadRow(
                    resume_id=resume_id,
                    candidate_id=candidate_id,
                    object_key=file.object_key,
                    media_type=file.media_type,
                    byte_size=byte_size,
                    # Stored for the UI only; never used as a filesystem path.
                    original_filename=original_filename,
                    uploaded_at=to_storage_utc(self._clock.now()),
                )
            )
            session.commit()

    def file_for(self, resume_id: str) -> FileRef | None:
        with self._factory() as session:
            row = session.get(ResumeUploadRow, resume_id)
            if row is None or row.deleted_at is not None:
                return None
            return FileRef(object_key=row.object_key, media_type=row.media_type)

    def mark_deleted(self, resume_id: str) -> None:
        """Record that the stored object was removed; keeps the audit row."""
        with self._factory() as session:
            row = session.get(ResumeUploadRow, resume_id)
            if row is not None:
                row.deleted_at = to_storage_utc(self._clock.now())
                session.commit()

    def list_for_candidate(self, candidate_id: str) -> Sequence[FileRef]:
        with self._factory() as session:
            rows = (
                session.execute(
                    select(ResumeUploadRow)
                    .where(ResumeUploadRow.candidate_id == candidate_id)
                    .where(ResumeUploadRow.deleted_at.is_(None))
                    .order_by(ResumeUploadRow.resume_id)
                )
                .scalars()
                .all()
            )
            return [FileRef(object_key=r.object_key, media_type=r.media_type) for r in rows]


class SqlCandidateEmbeddingRepository:
    """Resume vectors, keyed by profile version and embedding version."""

    def __init__(self, factory: sessionmaker[Session], clock: Clock):
        self._factory = factory
        self._clock = clock

    def save(self, record: EmbeddingRecord) -> None:
        now = to_storage_utc(self._clock.now())
        with self._factory() as session:
            key = (record.entity_id, record.entity_version, record.embedding_version)
            existing = session.get(CandidateEmbeddingRow, key)
            if existing is not None:
                # A rerun of the same versioned model must produce the same vector.
                if existing.vector != record.vector:
                    raise ConflictError(
                        "A stored vector cannot change without a new embedding version."
                    )
                return
            session.add(
                CandidateEmbeddingRow(
                    candidate_id=record.entity_id,
                    profile_version=record.entity_version,
                    embedding_version=record.embedding_version,
                    model_id=record.model_id,
                    model_revision=record.model_revision,
                    dimensions=record.dimensions,
                    preprocessing_version=record.preprocessing_version,
                    vector=list(record.vector),
                    created_at=now,
                )
            )
            session.commit()

    def get(
        self, candidate_id: str, profile_version: int, embedding_version: str
    ) -> EmbeddingRecord | None:
        with self._factory() as session:
            row = session.get(
                CandidateEmbeddingRow, (candidate_id, profile_version, embedding_version)
            )
            if row is None:
                return None
            return EmbeddingRecord(
                entity_id=row.candidate_id,
                entity_version=row.profile_version,
                vector=list(row.vector),
                model_id=row.model_id,
                model_revision=row.model_revision,
                dimensions=row.dimensions,
                preprocessing_version=row.preprocessing_version,
                embedding_version=row.embedding_version,
            )
