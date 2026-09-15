# Job source register (B-01)

Owner: M2. Status as of this writing: **no source is approved yet.** This is
the honest state, not a placeholder — see "Why nothing is approved" below
before treating any row here as usable.

Per plan.md: evaluate individual job-URL sources for permitted retrieval,
storage and display before implementing anything against them; implement one
approved single-posting adapter with synthetic fixtures; no discovery
crawler. "No assumption of JobThai/JobsDB access" was already established —
the same bar applies to every other candidate below.

## Why nothing is approved

Approving a source requires actually reading its current `robots.txt` and
Terms of Service, and completing one real retrieval against it. This
document was written in a sandboxed session whose network egress to
job/career sites is blocked by organization policy — confirmed directly, not
assumed:

```
$ curl --cacert <proxy CA> https://boards.greenhouse.io/robots.txt
curl: (56) CONNECT tunnel failed, response 403

WebFetch https://boards.greenhouse.io/robots.txt
{"error_type":"EGRESS_BLOCKED", "domain":"boards.greenhouse.io", ...}
```

The same block applies to every external domain tried (Greenhouse, RemoteOK,
We Work Remotely, JobThai, JobsDB). This is a property of *this execution
environment*, not a finding about any source's policy — do not read "blocked
here" as "blocked for the team." **A teammate (or this session running
somewhere with normal network access) must complete the live checks below
before any row moves from "candidate" to "approved," and before B-01's
acceptance bar ("one successful real retrieval") is met.**

## Candidates (desk research only — not independently verified this session)

| Source | Why it's a candidate | What still needs live verification |
| --- | --- | --- |
| A single company's Greenhouse-hosted job board (`boards.greenhouse.io/<company>` or the `boards-api.greenhouse.io` JSON endpoint) | Greenhouse's job board is widely used specifically for external embedding by companies that use it as their ATS; the JSON endpoint exists for exactly this kind of external read. | Fetch and read the actual current `robots.txt` for the specific company's board; read Greenhouse's current API terms (not a cached memory of them); confirm no login/CAPTCHA gate; do the one real retrieval. |
| A single company's Lever-hosted job board (`jobs.lever.co/<company>`) | Same pattern as Greenhouse: a common ATS with a public-facing board. | Same as above, for Lever's actual current terms and that specific board's `robots.txt`. |
| JobThai, JobsDB | Named directly in plan.md as the obvious "everyone assumes these work" case. | plan.md already flags these as unverified; nothing here changes that. Thai-market job boards' ToS commonly restrict automated retrieval — do not assume otherwise without reading the current text. |
| RemoteOK, We Work Remotely | Historically publish a public JSON/RSS feed intended for reuse. | Confirm the feed still exists at its documented location, confirm current terms, and that "public feed" actually covers this project's storage/display use (re-publishing full postings vs. linking out are different questions). |

None of these should be read as a recommendation to implement against
without the verification column being completed first. If Greenhouse/Lever
turn out permitted, a single company's board is the natural first target
precisely because plan.md asks for *one* approved single-posting adapter, not
a directory-wide crawler — and per-company boards are single postings by
construction, not a discovery surface.

## What is ready regardless of which source gets approved

`app/modules/jobs/sources/fetch.py` — `fetch_single_posting(url, allowed_hosts,
...)` — is a bounded, allow-listed single-URL fetch with an injectable
transport (no real network in its own tests; `tests/jobs/test_source_fetch.py`
covers it with a fake). It refuses non-HTTPS URLs and any host not in an
explicit allow-list before making a request, and bounds response size and
timeout. It does **not** attempt general SSRF hardening (redirect chains,
private-IP/DNS-rebinding defense, arbitrary-source support) — that is B-02's
job for the manual-import flow; this adapter's allow-list is closed to
whichever single host actually gets approved here.

Once a source clears live verification: add its host to the allow-list this
function is called with, note the evidence (dated `robots.txt`/ToS excerpt,
successful retrieval) in a new row here promoted from the candidates table
above, and this file's "no source is approved yet" line stops being true.

## Doing the live verification from a machine with normal network access

`app/modules/jobs/sources/verify_cli.py` turns "fetch robots.txt, read it,
try one retrieval" into one command instead of doing it by hand — run it from
anywhere that isn't this sandbox:

```bash
cd services/backend
uv run python -m app.modules.jobs.sources.verify_cli https://boards.greenhouse.io \
  --path /<company>/jobs/<id> \
  --fetch-sample https://boards.greenhouse.io/<company>/jobs/<id>
```

It prints the live `robots.txt`, evaluates whether the given path is allowed
(`app/modules/jobs/sources/robots.py`), and — with `--fetch-sample` — performs
the one real retrieval this file's acceptance bar asks for, printing the
status/content-type/size as evidence to paste into a new row above. It
deliberately does **not** read or evaluate Terms of Service; the tool's own
output says so, because robots.txt permission and ToS permission are
different questions and only a human can answer the second one.

