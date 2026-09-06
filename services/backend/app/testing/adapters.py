"""Predetermined fixture output only. No parsing, scoring or generation."""

from app.contracts.models import CandidateProfile, FileRef, FixtureBundle, JobPosting


class FixtureResumeProcessor:
    def __init__(self, fixtures: FixtureBundle):
        self.fixtures = fixtures

    def process(self, file: FileRef):
        if file.object_key != "fixture/resume-demo":
            raise NotImplementedError("Only the synthetic resume fixture is supported.")
        return self.fixtures.profiles[0].model_copy(deep=True)


class FixtureMatcher:
    def __init__(self, fixtures: FixtureBundle):
        self.fixtures = fixtures

    def score_pair(self, profile: CandidateProfile, job: JobPosting, scoring_version: str):
        for result in self.fixtures.matches:
            if (
                result.candidate_id,
                result.profile_version,
                result.job_id,
                result.job_version,
                result.scoring_version,
            ) == (
                profile.candidate_id,
                profile.profile_version,
                job.job_id,
                job.content_version,
                scoring_version,
            ):
                return result.model_copy(deep=True)
        raise NotImplementedError("No predetermined score for this fixture pair/version.")

    def match_job(self, job, active_profiles, scoring_version):
        return [self.score_pair(p, job, scoring_version) for p in active_profiles]

    def recommend(self, profile, corpus_snapshot, limit):
        if profile != self.fixtures.profiles[0] or corpus_snapshot != "fixture-initial":
            raise NotImplementedError("Only the initial recommendation fixture is supported.")
        return [r.model_copy(deep=True) for r in self.fixtures.recommendations.results[:limit]]


class FixtureExplainer:
    def __init__(self, fixtures: FixtureBundle):
        self.fixtures = fixtures

    def explain(self, profile, job, recommendation):
        explanation = self.fixtures.explanation
        if (
            profile.candidate_id,
            profile.profile_version,
            job.job_id,
            job.content_version,
            recommendation.revision,
        ) != (
            explanation.candidate_id,
            explanation.profile_version,
            explanation.job_id,
            explanation.job_version,
            explanation.revision,
        ):
            raise NotImplementedError("No explanation fixture for this version.")
        return explanation.model_copy(deep=True)
