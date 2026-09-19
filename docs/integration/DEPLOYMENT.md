# Deployment preparation (C-06)

**Status: host and budget chosen, not provisioned.** Nothing in this document has
been created in an AWS account or on any host. It records what the 2026-09-08
revision needs, the low-cost setup chosen on 2026-09-19 (D07), and how to bring
it up. Owner: M3 / Nai.

## What the revision changed

| Concern | Before (2026-09-07) | Now (2026-09-08) |
| --- | --- | --- |
| Resume originals | Private Railway bucket | **Private AWS S3 bucket** |
| NLP/embedding inference | CPU model inside the worker | **SageMaker endpoint**, with the in-process model kept for tests and parity |
| Retrieval | Stored vectors, exact cosine | Unchanged. **OpenSearch is still out of scope** |
| Explanations | Provider-neutral hosted LLM | Unchanged; **Bedrock is now an allowed provider**, not a requirement |
| Web/API/worker/PostgreSQL host | Railway proposed | **Decided 2026-09-19 (D07)**: Vercel for the web, Railway for API, worker and PostgreSQL |

Every cloud adapter has a local counterpart, so a fresh checkout runs, tests and
lints with no AWS account. See `services/backend/.env.example`.

## Chosen low-cost setup (decided 2026-09-19)

Plai chose the cheapest setup that keeps AWS limited to what the code needs.
Nothing below is provisioned yet.

| Part | Where | Plan |
| --- | --- | --- |
| Web (Next.js, `apps/web`) | Vercel | Hobby (free). Only `BACKEND_URL` is set there |
| API + worker | Railway | Hobby. Two services from `infra/backend.Dockerfile` |
| PostgreSQL | Railway | One instance, two databases and two roles |
| Resume originals | AWS S3 | One private bucket |
| Embeddings | AWS SageMaker **Serverless Inference** | Never a real-time endpoint |
| Explanations | AWS Bedrock | `LLM_PROVIDER=bedrock`, small model, pay per token |

Use one AWS region for S3, SageMaker and Bedrock (proposed `ap-southeast-1`),
after confirming the chosen Bedrock model is available there.

### Estimated monthly cost

Estimate only. Prices checked 2026-09-19 on
[Railway pricing](https://railway.com/pricing) and
[SageMaker pricing](https://aws.amazon.com/sagemaker/ai/pricing/). Bedrock
figures come from general model pricing and were not checked for the region.
Replace these estimates with the first measured bill.

| Item | Basis | Estimate |
| --- | --- | --- |
| Vercel | Hobby | $0 |
| Railway | $5/month Hobby including $5 usage; RAM $10/GB-month, vCPU $20/vCPU-month, volume $0.15/GB-month. Assumes 0.5-0.7 GB total RAM and near-idle CPU (unmeasured guess) | $5-8 |
| S3 | A few hundred small files | < $0.10 |
| SageMaker Serverless | $0.00004/s at 2 GB plus $0.016/GB processed (us-east-1 example); free tier 150,000 s/month for the first 2 months, for eligible accounts | < $1 |
| Bedrock | About 1,500 input + 400 output tokens per explanation; cached per revision | < $1-3 |
| **Total** | | **About $6-10/month** |

### Cost controls (set before use)

1. Never create a real-time SageMaker endpoint: it bills every hour it exists.
   Serverless bills per request; set `MaxConcurrency` to 1-2.
2. Create an AWS Budgets alert at $5 **before** creating the endpoint.
3. Set a hard Railway usage limit (for example $10) on the Hobby workspace.
4. The backend image installs no `ml` extra, so Railway containers never load a
   model; all inference goes to SageMaker.
5. After the demo or term, delete the serverless endpoint and stop the Railway
   services. Stopped Railway services are not billed.

### Railway specifics

- **Services:** `api` uses the image default command; `worker` overrides it
  with `python -m scripts.run_worker`. Keep one worker (see
  LOCAL_COMPLETION.md). The worker must never sleep.
- **Port:** the image listens on 8000. Set the service's target port to 8000,
  or override the start command to use `$PORT`.
- **PostgreSQL:** Railway provides one database and a superuser. Create the two
  roles and databases once with the SQL in `infra/postgres/init-databases.sh`,
  using fresh passwords. Then set `APP_DATABASE_URL` and `JOB_DATABASE_URL` on
  both services with their own role. Never use the superuser URL in the app.
- **Migrations:** run both Alembic chains as the API's pre-deploy command.
- **Secrets:** AWS keys, DB URLs, `IMPORT_ACCESS_TOKENS` and any LLM setting
  live only on Railway services. Vercel gets `BACKEND_URL` only, and never a
  `NEXT_PUBLIC_` secret.
- **AWS credentials:** Railway cannot assume an IAM role, so use one dedicated
  access key with the scoped policy below, plus `bedrock:InvokeModel` on the
  chosen model. Rotate it on a schedule.
- **Uploads:** Vercel may cap proxied request bodies below the 10 MB upload
  limit. Test a ~9 MB upload through the Vercel URL. If it fails, lower
  `MAX_UPLOAD_BYTES` or send uploads directly to the API.

### Step by step

Prepared files: `infra/railway/api.toml`, `infra/railway/worker.toml`,
`infra/railway/init-databases.sql`, `infra/aws/app-policy.json`,
`infra/aws/sagemaker-execution-policy.json` and
`infra/aws/deploy-serverless-endpoint.sh`. Replace the `REGION`, `ACCOUNT_ID`,
`RESUME_BUCKET` and Bedrock ARN placeholders before use.

Checked locally on 2026-09-19: `infra/backend.Dockerfile` builds (1.11 GB,
no torch), the image contains both Alembic configs and the worker, and the
`api.toml` start command serves `/health/ready` on a custom `$PORT`. Nothing
was deployed.

Steps marked **(owner)** need the account holder: account creation, sign-in,
payment and typing secrets are never done by an assistant.

1. **(owner)** Create the AWS account, enable MFA, and create a $5 AWS Budgets
   alert. Create the Railway (Hobby) and Vercel (Hobby) accounts.
2. **(owner)** In the chosen region, request access to the Bedrock model and
   note its model or inference-profile ARN.
3. Create the private S3 bucket (block public access, encryption, versioning).
4. Create an IAM user for Railway with `app-policy.json`, and a SageMaker
   execution role (trust `sagemaker.amazonaws.com`) with
   `sagemaker-execution-policy.json`. **(owner)** creates the access key.
5. Package the model (`uv run --extra ml python -m scripts.package_resume_model`),
   then run `deploy-serverless-endpoint.sh` with `CONFIRM_PAID_RESOURCES=yes`.
6. In Railway: add PostgreSQL, run `init-databases.sql` with `psql` against
   the superuser URL, then create services `api` and `worker` from this repo
   with the config paths above. Give `api` a public domain; give `worker` none.
7. **(owner)** Set variables on both services: `APP_ENV=production`,
   `APP_MODE=real`, both database URLs, `OBJECT_STORE_BACKEND=s3`,
   `RESUME_BUCKET`, `AWS_REGION`, `EMBEDDING_BACKEND=sagemaker`,
   `SAGEMAKER_EMBEDDING_ENDPOINT`, `SAGEMAKER_TIMEOUT_SECONDS=60`,
   `LLM_PROVIDER=bedrock`, `LLM_MODEL_ID`, `IMPORT_ACCESS_TOKENS`,
   `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`.
8. In Vercel: import the repository with Root Directory `apps/web` and set
   `BACKEND_URL=https://<api public domain>`.
9. Smoke test: `/health/ready` reports `mode: real`; upload a synthetic resume
   through the Vercel URL (also try ~9 MB); import one Greenhouse job; confirm
   ranked results and an explanation.

### To verify before calling it deployed

- Cold start: the model took about 30 s to load on a Windows CPU (A-07
  measurement). A serverless cold start may be similar, so start with
  `SAGEMAKER_TIMEOUT_SECONDS=60` and measure.

- The existing `SageMakerEmbeddingClient` uses `invoke_endpoint`, which
  Serverless Inference also uses. Parity against the A-07 model and
  cold-start time are unmeasured. If cold starts exceed
  `SAGEMAKER_TIMEOUT_SECONDS=30`, raise it.
- Measured Railway RAM/CPU, first bill, and the Bedrock model/region choice.

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
3. Deploy the embedding model (M1's A-07 artifact) as one **Serverless
   Inference** endpoint (2 GB memory, `MaxConcurrency` 1-2). Do not create a
   real-time instance endpoint.
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

- No AWS account, bucket, endpoint, Railway project or Vercel project exists
  yet. The host and budget are chosen, not provisioned.
- INT-02 (a live import against a permitted real URL, with real storage and LLM
  adapters) is not attempted and cannot be claimed from this document.
- CI does not deploy. It runs code, contract and database checks only.
