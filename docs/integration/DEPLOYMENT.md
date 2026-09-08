# Deployment preparation (C-06)

**Status: prepared, not provisioned.** Nothing in this document has been created
in an AWS account or on any host. It records what the 2026-09-08 revision needs,
what it costs attention, and how to bring it up when the team agrees a budget
(D07). Owner: M3 / Nai.

## What the revision changed

| Concern | Before (2026-09-07) | Now (2026-09-08) |
| --- | --- | --- |
| Resume originals | Private Railway bucket | **Private AWS S3 bucket** |
| NLP/embedding inference | CPU model inside the worker | **SageMaker endpoint**, with the in-process model kept for tests and parity |
| Retrieval | Stored vectors, exact cosine | Unchanged. **OpenSearch is still out of scope** |
| Explanations | Provider-neutral hosted LLM | Unchanged; **Bedrock is now an allowed provider**, not a requirement |
| Web/API/worker/PostgreSQL host | Railway proposed | **Open (D07)**: Railway or an AWS-native host |

Every cloud adapter has a local counterpart, so a fresh checkout runs, tests and
lints with no AWS account. See `services/backend/.env.example`.

## Services

| Service | Command | Notes |
| --- | --- | --- |
| Web | `pnpm start` (`infra/web.Dockerfile`) | Proxies `/backend/*` to the API using the server-side `BACKEND_URL` |
| API | `uvicorn app.main:app` (`infra/backend.Dockerfile`) | Loads no model; readiness at `/health/ready` |
| Worker | `python -m scripts.run_worker` | The only consumer of the durable queue, and the only process that calls the model |
| PostgreSQL | one instance, two databases | `career_app` and `career_jobs` with separate roles, URLs and migration chains |
| S3 | one private bucket | Resume originals under `RESUME_OBJECT_PREFIX` |
| SageMaker | one inference endpoint | Embeddings; billed per endpoint-hour |

The worker is not optional and not a cron job. Pending work waits for a running
consumer, so "always-on matching" and "a worker that sleeps" cannot both be true.

## AWS setup, in order

1. Agree the account owner, region and budget (D07). Create an AWS Budgets alert
   **before** the first endpoint exists.
2. Create the bucket. Block all public access, enable default encryption and
   versioning, and set a lifecycle rule matching the retention decided in D06.
   The application never issues a public or presigned URL: every read is
   authorized by the API, so the bucket needs no public path at all.
3. Deploy the embedding model (M1's A-07 artifact) to one endpoint. Start with
   the smallest CPU instance that fits the model and record its cost per hour.
4. Create one IAM role per service with only these permissions:

   ```text
   API and worker:
     s3:GetObject, s3:PutObject, s3:DeleteObject
       on arn:aws:s3:::<RESUME_BUCKET>/<RESUME_OBJECT_PREFIX>*
     sagemaker:InvokeEndpoint
       on arn:aws:sagemaker:<region>:<account>:endpoint/<endpoint-name>
     bedrock:InvokeModel (only if LLM_PROVIDER=bedrock)
       on the single selected model
   ```

   Prefer an instance or task role. If the chosen host cannot assume one, use a
   dedicated access key with the same policy and rotate it on a schedule; never
   commit it, and never expose it through a `NEXT_PUBLIC_` variable.
5. Set the environment from `services/backend/.env.example`, with
   `APP_MODE=real`. `Settings.validate_for_runtime()` refuses to start a
   production process that still points at a local adapter or the fake LLM, so a
   misconfigured deployment fails at startup instead of quietly serving mocks.
6. Run both migration chains, in either order - they are independent:

   ```bash
   uv run alembic -c alembic-app.ini upgrade head
   uv run alembic -c alembic-jobs.ini upgrade head
   ```

7. Start the API, then the worker. Check `/health/ready` reports `mode: real`
   and names the adapters it will use.

## Cost attention

- A SageMaker endpoint bills for every hour it exists, whether or not anything
  calls it. At this corpus size it is the largest and least obvious line item.
  Decide an explicit start/stop policy, or accept the standing cost knowingly.
- S3 charges for storage, requests and egress. Resume originals are small; a
  cross-provider host (an AWS bucket with a non-AWS application) adds egress on
  every read, which is one input into D07.
- LLM calls are billed separately from everything above.
- Record measured cost after the first sample run. Nothing here is a quoted
  price.

## Rollback

1. Application: redeploy the previous image tag. The images carry no state.
2. Database: both chains have a `downgrade`, but a downgrade that drops a table
   loses candidate data. Prefer forward-only fixes; if a downgrade is
   unavoidable, restore from a snapshot taken immediately before the upgrade.
3. Model or embedding version: point `SAGEMAKER_EMBEDDING_ENDPOINT` back at the
   previous endpoint and rebuild vectors. Stored vectors carry their model
   revision, so mixed-version scores are rejected rather than silently compared.
4. Queue: parked (`failed`) rows stay readable. Fix the cause and re-enqueue;
   `event_id` deduplication makes a replay safe.

## Not done here

- No AWS account, bucket, endpoint, host or budget exists yet.
- INT-02 (a live import against a permitted real URL, with real storage and LLM
  adapters) is not attempted and cannot be claimed from this document.
- CI does not deploy. It runs code, contract and database checks only.
