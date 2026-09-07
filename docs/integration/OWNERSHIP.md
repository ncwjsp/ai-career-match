# Ownership after bootstrap review

Plai (M1) published SET-01 and initial SET-02. M3 takes shared files/contracts
under that handoff; Plai requested the 2026-09-07 scope-document revision. No GitHub handles were supplied, so CODEOWNERS is deferred.

| Owner | Exclusive paths |
| --- | --- |
| M1 / Plai | backend app/nlp, app/modules/resume, tests/nlp, tests/resume; web features/upload and features/profile; ml/resume; docs/resume |
| M2 | backend alembic-jobs.ini, app/db/jobs, migrations/jobs, app/modules/jobs, app/modules/matching, app/search, tests/jobs, tests/matching, tests/search; web features/job-import and co-located tests (planned); ml/matching; research; docs/job-sources and docs/matching |
| M3 | Root config/plan/docs, CI, backend contracts/core/api/main/orchestration, alembic-app.ini, app/db/app, migrations/app, explanations/integration tests, web app/shared UI/API client/results/detail, infra |

Canonical contracts and generated types have one editor (M3). M1/M2 propose
changes and review producer/consumer compatibility. Each database has its own
migration chain. Do not edit another member's folders while developing a feature.
The public DTOs belong to contracts; domain implementations belong to their owners.


M3 also owns app/testing, scripts, tests/core, tests/contracts, and the generated API files. M2 requests shared infrastructure/CI changes through M3; M1/M2 do not edit shared dependency manifests concurrently. All backend paths above are relative to services/backend, and web paths to apps/web/src.

## Manual import and Railway coordination

M2 owns the planned import component under `apps/web/src/features/job-import/`
and the importer/jobs router. M3 alone edits `apps/web/src/app/` to mount it,
shared client/types, server-side import access, queue integration and deployment.
Freeze the import request/status protocol together before integration. Existing
`JobIngestor.run(source_id)` does not yet describe the new URL flow.

M3 prepares Railway web/API/worker/PostgreSQL and a private bucket, while M2
owns job-vector persistence/retrieval. M1 owns CPU model packaging. No owner
needs to create cron, OpenSearch, SageMaker, Bedrock or AWS storage resources.
Keep separate application/job migrations and shared dependency PRs. The scope
change does not transfer resume or matching implementation to another member.
