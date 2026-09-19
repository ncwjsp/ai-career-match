# Job source register (B-01)

Owner: M2. Status as of 2026-09-19: **three sources are approved** — the
Greenhouse, Lever and Ashby hosted single-company job boards. See "Approved
sources" below for the evidence and "Checked and not approved" for sites that
were ruled out. The code-side list is `app/modules/jobs/sources/approved.py`;
keep the two in step.

Per plan.md: evaluate individual job-URL sources for permitted retrieval,
storage and display before implementing anything against them; implement one
approved single-posting adapter with synthetic fixtures; no discovery
crawler. "No assumption of JobThai/JobsDB access" was already established —
the same bar applies to every other candidate below.

## Approved sources

### Greenhouse-hosted single-company job boards (`job-boards.greenhouse.io`)

Pattern: `https://job-boards.greenhouse.io/<company>/jobs/<id>`, e.g.
`https://job-boards.greenhouse.io/greenhouse/jobs/8148418?gh_jid=8148418`.
Note the current host is `job-boards.greenhouse.io`, not the older
`boards.greenhouse.io` this document originally guessed from background
knowledge — a concrete reminder that only a live check of the real URL is
trustworthy here, not recollection.

Verified live (not desk research) on 2026-09-15, from a machine with normal
network access — this sandboxed session's own egress to job/career domains
is still blocked (see "Why the sandbox couldn't do this itself" below), so a
teammate ran the checks using `verify_cli.py`:

1. **robots.txt** — fetched `https://job-boards.greenhouse.io/robots.txt`
   live. Every `Disallow` directive in the file is commented out, i.e. the
   file declares no crawl restrictions at all. `evaluate()`
   (`app/modules/jobs/sources/robots.py`) confirms
   `can_fetch("ai-career-match-job-source/0.1", "/greenhouse/jobs/8148418") == True`.
2. **Real retrieval** — `fetch_single_posting()` against
   `https://job-boards.greenhouse.io/greenhouse/jobs/8148418?gh_jid=8148418`
   returned `HTTP 200, text/html, 86653 chars`. This is the "one successful
   real retrieval" B-01's acceptance bar asks for.
3. **Terms of Service** — read Greenhouse's general Terms of
   Service/Terms of Use at `https://www.greenhouse.com/legal` (the corporate
   `.com` site's legal hub, not the `.io` job-board host's own hub, which
   only lists Privacy Policy / Master Subscription Agreement / Data
   Processing Addendum / CCPA notice / Bias audit / Cookie notice /
   Subprocessors / Sustainability — none of which govern a third party
   reading public postings; the MSA and DPA are explicit that they apply
   only "if your company has a Greenhouse subscription"). The general
   Terms of Service/Terms of Use document contains **no prohibition** on
   automated access, reproduction, or third-party use of publicly displayed
   job postings — checked for, and did not find, any of: automated, robot,
   scrape, crawl, bot, reproduce, republish, copy, extract, commercial use.
   This is an absence-of-prohibition finding, not an explicit written grant
   — worth being honest about that distinction — but combined with a fully
   permissive `robots.txt` and content served with no login/paywall gate, it
   is a reasonable basis to approve.

### Lever-hosted job boards (`jobs.lever.co`) — approved 2026-09-19

Pattern: `https://jobs.lever.co/<company>/<posting-id>`. Checked live on
2026-09-19 by Claude (assistant) for Plai; a team member should re-read the
ToS before the final report.

1. **robots.txt** — `User-agent: *` / `Allow: /`.
2. **Real retrieval** — `https://jobs.lever.co/palantir/ac978161-6f46-4f6b-ad9e-a258e642751c`
   returned HTTP 200 `text/html` with no redirect and a schema.org
   `JobPosting` JSON-LD block. `import_cli` stored it end to end (title,
   company, 4,572-character description) in a scratch `career_jobs`.
3. **Terms** — Lever's Terms of Service bind customers who sign an Order Form;
   no clause restricts third-party visitors reading public postings. Lever's
   own Postings API documentation states that published postings are
   publicly viewable and may be scraped by third parties. Absence of a
   prohibition, not a written grant.

### Ashby-hosted job boards (`jobs.ashbyhq.com`) — approved 2026-09-19

Pattern: `https://jobs.ashbyhq.com/<company>/<posting-id>`. Same checker and
caveat as Lever.

1. **robots.txt** — `User-Agent: *` disallows only `/meeting/`, `/b/` and
   `/api/`; posting pages are allowed.
2. **Real retrieval** — `https://jobs.ashbyhq.com/ashby/7458d4e9-da2e-47bd-98cb-adfda43d42b2`
   returned HTTP 200 `text/html`, no redirect, with `JobPosting` JSON-LD;
   stored end to end by `import_cli`.
3. **Terms** — Ashby's customer terms bind paying customers only; no clause
   restricts visitors reading public job boards. Absence of a prohibition.

Content on every approved board still belongs to the hiring company. Store
and show it for this course project only, keep the source link on each job,
and do not republish postings elsewhere.

**Allow-list:** `APPROVED_HOSTS` in `app/modules/jobs/sources/approved.py`
(`job-boards.greenhouse.io`, `jobs.lever.co`, `jobs.ashbyhq.com`). The API,
the `/job-import` page and `import_cli` all use it, and each import is
recorded under its own host's `source_id`.

## Checked and not approved (2026-09-19)

Live robots.txt checks from a normal network on 2026-09-19. "ToS not read"
means the site was not pursued, not that it is permitted.

| Source | Finding | Decision |
| --- | --- | --- |
| LinkedIn (`www.linkedin.com`) | robots.txt: `User-agent: *` / `Disallow: /` | Not allowed |
| JobsDB (`th.jobsdb.com`) | robots.txt disallows `*/job/` and `*?` for every agent | Not allowed. Only a person copying text in by hand could work, pending ToS |
| JobThai (`www.jobthai.com`) | robots.txt allows `/`, but the job-seeker ToS forbids reproducing, copying, modifying or disseminating site content without prior written consent | Not allowed without written permission (contact support@jobthai.com) |
| Indeed, Glassdoor, Wellfound | robots.txt has partial rules for job pages; ToS not read | Not pursued |
| SmartRecruiters (`jobs.smartrecruiters.com`) | Job page has no `JobPosting` JSON-LD; Posting API needs an API key | Not pursued |
| Workable (`apply.workable.com`) | robots.txt permissive; no sample posting retrieved | Candidate: needs a real retrieval and ToS check |
| RemoteOK (`remoteok.com/api`) | Public JSON API; its API terms require a followed link back to Remote OK and naming it as the source | Candidate: needs a feed adapter and visible attribution |
| We Work Remotely | robots.txt allows job pages; ToS not read | Candidate |

A new candidate needs the same three checks as the approved rows, then one
line in `approved.py` plus its evidence here.

## Why the sandbox couldn't do this itself

This document was originally written in a sandboxed session whose network
egress to job/career sites is blocked by organization policy — confirmed
directly, not assumed:

```
$ curl --cacert <proxy CA> https://boards.greenhouse.io/robots.txt
curl: (56) CONNECT tunnel failed, response 403

WebFetch https://boards.greenhouse.io/robots.txt
{"error_type":"EGRESS_BLOCKED", "domain":"boards.greenhouse.io", ...}
```

The same block applies to every external domain tried (Greenhouse, RemoteOK,
We Work Remotely, JobThai, JobsDB). This is a property of *that execution
environment*, not a finding about any source's policy. `verify_cli.py` (see
below) was built so a teammate with normal network access could complete the
live checks themselves in one command instead of by hand — which is how the
Greenhouse row above got its evidence.

## What is ready regardless of which source gets approved

`app/modules/jobs/sources/fetch.py` — `fetch_single_posting(url, allowed_hosts,
...)` — is a bounded, allow-listed single-URL fetch with an injectable
transport (no real network in its own tests; `tests/jobs/test_source_fetch.py`
covers it with a fake). It refuses non-HTTPS URLs and any host not in an
explicit allow-list before making a request, and bounds response size and
timeout. It does **not** attempt general SSRF hardening (redirect chains,
private-IP/DNS-rebinding defense, arbitrary-source support) — that is B-02's
job for the manual-import flow; this adapter's allow-list is closed to the
approved hosts (see "Approved sources" above).

When another candidate clears live verification: add its host to the
allow-list `fetch_single_posting()` is called with, note the evidence (dated
`robots.txt`/ToS excerpt, successful retrieval) in a new row under "Approved
sources" promoted from the candidates table above.

## Doing the live verification from a machine with normal network access

`app/modules/jobs/sources/verify_cli.py` turns "fetch robots.txt, read it,
try one retrieval" into one command instead of doing it by hand. Example
against the already-approved Greenhouse host:

```bash
cd services/backend
uv run python -m app.modules.jobs.sources.verify_cli https://job-boards.greenhouse.io \
  --path /<company>/jobs/<id> \
  --fetch-sample https://job-boards.greenhouse.io/<company>/jobs/<id>
```

It prints the live `robots.txt`, evaluates whether the given path is allowed
(`app/modules/jobs/sources/robots.py`), and — with `--fetch-sample` — performs
the one real retrieval this file's acceptance bar asks for, printing the
status/content-type/size as evidence to paste into a new row above. It
deliberately does **not** read or evaluate Terms of Service; the tool's own
output says so, because robots.txt permission and ToS permission are
different questions and only a human can answer the second one.

