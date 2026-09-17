"""A-05 durable extraction/profile stages; matching remains the M2/M3 event flow."""

from sqlalchemy import select

from app.contracts.models import ErrorDetail, ProfileReadyEvent
from app.core.errors import AppError, Forbidden
from app.core.ids import new_token
from app.core.timeutil import from_storage_utc
from app.db.app.models import AnalysisRunRow, CandidateRow, WorkQueueRow
from app.modules.matching.text import profile_text
from app.modules.resume.errors import ResumeExtractionError
from app.modules.resume.extraction import extract_resume
from app.modules.resume.lease import LostLease, keep_lease
from app.modules.resume.profile import build_candidate_profile
from app.modules.resume.types import ExtractionLimits
from app.nlp.embeddings import EMBEDDING_VERSION, VersionedEmbedder
from app.nlp.errors import NlpError
from app.nlp.processor import SharedTextProcessor
from app.nlp.remote import SageMakerNlpProcessor


def event_id(analysis_id):
    return f"profile-ready-{analysis_id}"


class ResumeWorker:
    def __init__(self, container, processor_factory=None):
        self.c = container
        self.processor_factory = processor_factory or self._processor

    def _processor(self, resume_id):
        if self.c.settings.embedding_backend == "sagemaker":
            return SageMakerNlpProcessor(self.c.settings)
        return SharedTextProcessor(resume_id, 1)

    def step(self):
        self.finish_matching()
        owner = new_token()
        maintenance = self.c.analysis_queue.maintenance
        claimed = self.c.analysis_queue.claim(owner)
        if claimed is None:
            return False
        queued_run, file = claimed
        run = self.c.analyses.get(queued_run.analysis_id)
        if run is None or run.state in {"failed", "ready"}:
            maintenance.acknowledge(queued_run.analysis_id, owner)
            return True
        try:
            with keep_lease(maintenance, run.analysis_id, owner) as check:
                self.process(run, file, check)
        except LostLease:
            return True
        except ResumeExtractionError as error:
            if maintenance.renew(run.analysis_id, owner):
                self.c.analyses.fail(run.analysis_id, error.as_detail(run.analysis_id))
        except NlpError as error:
            if maintenance.renew(run.analysis_id, owner):
                self.fail(run, error.code, str(error))
        except AppError as error:
            if error.retryable:
                maintenance.retry(run.analysis_id, error.code, owner)
                self.finish_matching()
                return True
            if maintenance.renew(run.analysis_id, owner):
                self.fail(run, error.code, error.message)
        except Exception:
            # Never put document contents, filenames or exception strings into logs/queue.
            maintenance.retry(run.analysis_id, "PROCESSING_FAILED", owner)
            self.finish_matching()
            return True
        maintenance.acknowledge(run.analysis_id, owner)
        return True

    def fail(self, run, code, message):
        self.c.analyses.fail(
            run.analysis_id,
            ErrorDetail(
                code=code,
                message=message,
                retryable=False,
                request_id=run.analysis_id,
            ),
        )

    def process(self, run, file, check=lambda: None):
        c = self.c
        with c.app_sessions() as session:
            candidate = session.get(CandidateRow, run.candidate_id)
            if candidate is None or not candidate.matching_enabled:
                raise Forbidden("The candidate is no longer available for matching.")
            expiry = from_storage_utc(candidate.expires_at)
            if expiry <= c.clock.now():
                raise Forbidden("The candidate retention period has expired.")
        profile = c.profiles.get(run.candidate_id)
        if profile is None or profile.resume_id != run.resume_id:
            version = profile.profile_version + 1 if profile else 1
            c.analyses.advance(run.analysis_id, "extracting")
            filename = "resume.pdf" if file.media_type == "application/pdf" else "resume.docx"
            extracted = extract_resume(
                c.object_store.read(file),
                filename=filename,
                document_id=run.resume_id,
                document_version=1,
                media_type=file.media_type,
                limits=ExtractionLimits(max_file_bytes=c.settings.max_upload_bytes),
            )
            c.analyses.advance(run.analysis_id, "profiling")
            source = extracted.content.model_copy(update={"language": "en"})
            analysis = self.processor_factory(run.resume_id).analyze(source, "en")
            profile = build_candidate_profile(
                analysis,
                candidate_id=run.candidate_id,
                resume_id=run.resume_id,
                profile_version=version,
                matching_enabled=True,
                expires_at=expiry,
                as_of=run.created_at.date(),
                extraction_warnings=extracted.warnings,
            )
            check()
            c.profiles.save(profile)
        if (
            c.candidate_embeddings.get(run.candidate_id, profile.profile_version, EMBEDDING_VERSION)
            is None
        ):
            # Reuse M2's existing profile representation so stored and pairwise
            # embeddings use identical text, normalization and model versions.
            from app.contracts.models import ProcessedText
            from app.nlp.types import PREPROCESSING_VERSION

            text = profile_text(profile)
            if not text.strip():
                raise NlpError(
                    "NO_SUPPORTED_PROFILE_FACTS",
                    "No supported profile facts were found. Use clear English resume sections.",
                )
            source = ProcessedText(
                text=text,
                language="en",
                evidence=profile.evidence,
                preprocessing_version=PREPROCESSING_VERSION,
            )
            record = VersionedEmbedder(c.embedding_client).encode_entity(
                source, run.candidate_id, profile.profile_version
            )
            check()
            c.candidate_embeddings.save(record)
        # Replaying after a crash reuses the immutable profile and event identity.
        check()
        c.match_queue.enqueue(
            ProfileReadyEvent(
                event_id=event_id(run.analysis_id),
                event_type="profile.ready",
                candidate_id=run.candidate_id,
                profile_version=profile.profile_version,
                occurred_at=run.created_at,
            )
        )
        c.analyses.advance(run.analysis_id, "matching", warnings=profile.extraction_warnings)

    def finish_matching(self):
        """Run without a browser: reconcile matching and parked analysis work."""
        c = self.c
        with c.app_sessions() as session:
            ids = list(
                session.scalars(
                    select(AnalysisRunRow.analysis_id)
                    .where(AnalysisRunRow.state.not_in(["ready", "failed"]))
                    .limit(1000)
                )
            )
        for analysis_id in ids:
            run = c.analyses.get(analysis_id)
            if run is None:
                continue
            with c.app_sessions() as session:
                analysis_work = session.get(WorkQueueRow, analysis_id)
                match_work = session.get(WorkQueueRow, event_id(analysis_id))
                failed = (analysis_work and analysis_work.state == "failed") or (
                    match_work and match_work.state == "failed"
                )
            if failed:
                self.fail(
                    run,
                    "PROCESSING_FAILED",
                    "Processing failed after bounded retries. Upload again or contact the team.",
                )
            elif run.state == "matching":
                recommendations = c.recommendations.latest(run.candidate_id)
                profile = c.profiles.get(run.candidate_id)
                if profile and profile.expires_at <= c.clock.now():
                    self.fail(run, "CANDIDATE_EXPIRED", "The retention period has expired.")
                    continue
                if (
                    recommendations
                    and profile
                    and recommendations.profile_version == profile.profile_version
                ):
                    c.analyses.advance(
                        analysis_id,
                        "ready",
                        result_count=len(recommendations.results),
                        corpus_snapshot=(
                            recommendations.results[0].index_version
                            if recommendations.results
                            else "empty-corpus"
                        ),
                    )
