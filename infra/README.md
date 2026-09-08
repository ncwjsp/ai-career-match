# infra

| File | Purpose |
| --- | --- |
| `compose.yaml` | Local PostgreSQL with both databases and separate roles. Development only. |
| `postgres/init-databases.sh` | Creates `career_app` / `career_jobs` and their roles on an empty volume. |
| `backend.Dockerfile` | One image for the API and the worker; the worker overrides the command. |
| `web.Dockerfile` | The Next.js frontend. |

Deployment steps, the AWS S3 and SageMaker setup from the 2026-09-08 revision,
IAM scoping, cost attention and rollback live in
[docs/integration/DEPLOYMENT.md](../docs/integration/DEPLOYMENT.md).
Nothing here has been provisioned.
