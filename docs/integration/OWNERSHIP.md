# Ownership after bootstrap review

Plai (M1) prepares SET-01 and initial SET-02. M3 takes shared files after the
review/commit handoff. No GitHub handles were supplied, so CODEOWNERS is deferred.

| Owner | Exclusive paths |
| --- | --- |
| M1 / Plai | backend app/nlp, app/modules/resume, tests/nlp, tests/resume; web features/upload and features/profile; ml/resume; docs/resume |
| M2 | backend app/db/jobs, migrations/jobs, app/modules/jobs, app/modules/matching, app/search, tests/jobs, tests/matching, tests/search; ml/matching; research; docs/job-sources and docs/matching |
| M3 | Root config/plan/docs, CI, backend contracts/core/api/main/orchestration, app/db/app, migrations/app, explanations/integration tests, web app/shared UI/API client/results/detail, infra |

Canonical contracts and generated types have one editor (M3). M1/M2 propose
changes and review producer/consumer compatibility. Each database has its own
migration chain. Do not edit another member's folders while developing a feature.
The public DTOs belong to contracts; domain implementations belong to their owners.
