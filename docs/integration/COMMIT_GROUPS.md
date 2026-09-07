# Two focused commit groups

> Historical bootstrap record. SET-01 (`0a00918`) and initial SET-02
> (`858c58b`) are now published on main at
> [ncwjsp/ai-career-match](https://github.com/ncwjsp/ai-career-match).
> Pre-commit/staging/remote statements and commands below describe the original
> delivery snapshot; do not rerun them. GitHub CI results are still unverified
> here. Use [START_HERE.md](../../START_HERE.md) and [plan.md](../../plan.md)
> for current task orders and the 2026-09-07 manual-import/Railway scope.


At delivery, Git is initialized on main with **no commits and no remote**.
SET-01 is already staged. SET-02 is in the remaining working-tree changes and
untracked source files. Some files appear as AM: their staged version belongs
to SET-01 and their newer working version belongs to SET-02.

**Do not run git add . before committing SET-01:** that would combine the groups.
These commands are for Plai to run after review; no commit has been made for you.

## 1. SET-01 — runnable foundation

Review the staged snapshot, then commit it:

```bash
git status --short
git diff --cached --stat
git diff --cached
git commit -m "chore: bootstrap shared project foundation (SET-01)"
```

Includes initial plan/starter guide, ownership scaffolds, README, ignores/env
examples, locked runtime/dependency workflows, Next shell, FastAPI health,
separate local database provisioning/migration runners and minimal CI.
This snapshot's backend has only health routes and core tests; it has no
dependency on the second group's untracked contracts.

Next-generated AGENTS.md/CLAUDE.md are included so running next dev does not
create surprising untracked instructions. next-env.d.ts stays generated/ignored.

## 2. Initial SET-02 — contracts, fixtures and handoff

After the first commit, stage these explicit paths from the repository root.
Each line is a separate command and works in PowerShell or a POSIX shell.

```bash
git add .github/workflows/ci.yml README.md START_HERE.md plan.md
git add apps/web/package.json apps/web/scripts apps/web/src/lib/api
git add contracts/README.md contracts/openapi.json contracts/examples/bootstrap.json
git add docs/integration docs/sources/README.md
git add services/backend/app/main.py services/backend/app/api services/backend/app/contracts
git add services/backend/app/testing services/backend/scripts/export_openapi.py services/backend/scripts/demo_handoff.py
git add services/backend/tests/contracts services/backend/tests/integration
git diff --cached --check
git diff --cached --stat
git diff --cached
git commit -m "feat: define v1 contracts and fixtures (SET-02)"
git status --short
```

Includes canonical DTOs/ports, planned HTTP signatures, typed 501/422 responses,
generated API/frontend snapshots, fixed synthetic adapters and examples, both
matching-trigger tests/demo, schema/DB CI checks, evidence-based tracker updates,
source checksums and ownership transfer.

Review unexpected remaining files before staging them. Local environments,
dependencies, caches, build outputs and private data are ignored. The ignored
.review directory contains temporary verification snapshots; it is not source.

## Publish and branch afterward

Record both hashes in BOOTSTRAP_HANDOFF.md. A later tracking-only commit is fine.
Configure your own Git author identity if Git asks; do not use a teammate's identity.

No actual GitHub target has been supplied. Supply/create the intended repository
yourself, review its visibility, then use the publication steps in START_HERE.md.
After both checkpoints are available on main, teammates clone that checkpoint
and start their assigned branches. Plai can begin A-01 immediately after committing;
M2/M3 do not need to wait for a finished resume parser.
