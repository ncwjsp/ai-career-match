"""A-05 intake unit of work. Application ORM tables remain owned by M3."""

from sqlalchemy import select

from app.contracts.models import AnalysisRun, UploadAccepted
from app.core.errors import ConflictError, Forbidden, NotFound
from app.core.ids import new_id
from app.core.timeutil import from_storage_utc, to_storage_utc
from app.db.app.models import (
    AnalysisRunRow,
    CandidateProfileRow,
    CandidateRow,
    ResumeUploadRow,
    WorkQueueRow,
)


class ResumeService:
    def __init__(self, container):
        self.c = container

    def accept(self, candidate_id, data, media_type):
        c = self.c
        now = c.clock.now()
        stored_now = to_storage_utc(now)
        resume_id, analysis_id = new_id("resume"), new_id("analysis")
        file = c.object_store.put(data, media_type)
        try:
            # Serialize uploads for the same retained candidate. Metadata and queue
            # commit together; never return 202 for an upload without durable work.
            with c.app_sessions() as session, session.begin():
                candidate = session.scalar(
                    select(CandidateRow)
                    .where(CandidateRow.candidate_id == candidate_id)
                    .with_for_update()
                )
                if candidate is None or from_storage_utc(candidate.expires_at) <= now:
                    raise Forbidden("This candidate session has expired.")
                active = session.scalar(
                    select(AnalysisRunRow.analysis_id).where(
                        AnalysisRunRow.candidate_id == candidate_id,
                        AnalysisRunRow.state.not_in(["ready", "failed"]),
                    )
                )
                if active:
                    raise ConflictError(
                        "A resume is already being processed. Wait for it to finish."
                    )
                run = AnalysisRun(
                    analysis_id=analysis_id,
                    candidate_id=candidate_id,
                    resume_id=resume_id,
                    state="queued",
                    created_at=now,
                    updated_at=now,
                    corpus_snapshot=None,
                    warnings=[],
                    error=None,
                    result_count=0,
                )
                session.add(
                    ResumeUploadRow(
                        resume_id=resume_id,
                        candidate_id=candidate_id,
                        object_key=file.object_key,
                        media_type=file.media_type,
                        byte_size=len(data),
                        original_filename=None,
                        uploaded_at=stored_now,
                    )
                )
                session.add(
                    AnalysisRunRow(
                        **{
                            **run.model_dump(exclude={"created_at", "updated_at"}),
                            "created_at": stored_now,
                            "updated_at": stored_now,
                        }
                    )
                )
                session.add(
                    WorkQueueRow(
                        event_id=analysis_id,
                        queue="analysis",
                        event_type="analysis.requested",
                        payload={
                            "run": run.model_dump(mode="json"),
                            "file": file.model_dump(mode="json"),
                        },
                        state="pending",
                        attempts=0,
                        max_attempts=5,
                        available_at=stored_now,
                        created_at=stored_now,
                        updated_at=stored_now,
                    )
                )
        except Exception:
            # Compensate external storage after a known failed DB transaction.
            c.object_store.delete(file)
            raise
        return UploadAccepted(
            candidate_id=candidate_id,
            resume_id=resume_id,
            analysis_id=analysis_id,
            status_url=f"/api/v1/analyses/{analysis_id}",
        )

    def profile(self, candidate_id, resume_id):
        with self.c.app_sessions() as session:
            row = session.scalar(
                select(CandidateProfileRow)
                .where(
                    CandidateProfileRow.candidate_id == candidate_id,
                    CandidateProfileRow.resume_id == resume_id,
                )
                .order_by(CandidateProfileRow.profile_version.desc())
            )
            if row is None:
                raise NotFound("No profile is available for this resume in this session.")
            version = row.profile_version
        return self.c.profiles.get(candidate_id, version)
