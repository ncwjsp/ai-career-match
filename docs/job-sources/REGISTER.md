# Job source register (B-01)

Owner: M2. Status as of this writing: **one source is approved** —
Greenhouse-hosted single-company job boards (`job-boards.greenhouse.io`).
See "Approved sources" below for the evidence. Everything else in the
candidates table is still unverified.

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

**Allow-list:** `job-boards.greenhouse.io` is the host to pass in
`allowed_hosts` when calling `fetch_single_posting()`. B-02's import flow is
what will actually wire this in as its caller.

## Candidates (desk research only — not independently verified)

| Source | Why it's a candidate | What still needs live verification |
| --- | --- | --- |
| A single company's Lever-hosted job board (`jobs.lever.co/<company>`) | Same pattern as Greenhouse: a common ATS with a public-facing board. | Fetch and read that host's actual current `robots.txt`; read Lever's current Terms of Service; confirm no login/CAPTCHA gate; do one real retrieval. |
| JobThai, JobsDB | Named directly in plan.md as the obvious "everyone assumes these work" case. | plan.md already flags these as unverified; nothing here changes that. Thai-market job boards' ToS commonly restrict automated retrieval — do not assume otherwise without reading the current text. |
| RemoteOK, We Work Remotely | Historically publish a public JSON/RSS feed intended for reuse. | Confirm the feed still exists at its documented location, confirm current terms, and that "public feed" actually covers this project's storage/display use (re-publishing full postings vs. linking out are different questions). |

None of these should be read as a recommendation to implement against
without the verification column being completed first. Greenhouse being
approved already satisfies B-01's "one approved single-posting adapter"
requirement — these remain candidates for later expansion, not blockers.

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
job for the manual-import flow; this adapter's allow-list is closed to
`job-boards.greenhouse.io` for now (see "Approved sources" above).

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

