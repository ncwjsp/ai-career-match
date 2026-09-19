"use client";

import { useState } from "react";
import { importJob } from "@/lib/api/client";

export function JobImport() {
  const [url, setUrl] = useState("");
  const [token, setToken] = useState("");
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  async function submit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setBusy(true); setError(null); setMessage(null);
    try {
      const result = await importJob(url.trim(), token.trim());
      if (result.warnings.length) setError(result.warnings.join(" "));
      else setMessage(result.new_jobs ? "Job added. Matching will update for active candidates." : result.changed_jobs ? "Job updated. Matching will refresh automatically." : "This job is already up to date.");
    } catch (error) {
      setError(error instanceof Error ? error.message : "Unable to import this job.");
    } finally { setBusy(false); }
  }

  return <form onSubmit={submit} className="mt-8 max-w-xl space-y-5">
    <p>Paste a single Greenhouse job posting URL. Paste it again later to check for changes.</p>
    <div><label htmlFor="job-url" className="block font-medium">Job URL</label>
      <input id="job-url" type="url" required maxLength={2048} value={url} onChange={event => setUrl(event.target.value)} placeholder="https://job-boards.greenhouse.io/company/jobs/123" className="mt-2 w-full rounded border p-3" /></div>
    <div><label htmlFor="team-token" className="block font-medium">Team access token</label>
      <input id="team-token" type="password" required autoComplete="off" value={token} onChange={event => setToken(event.target.value)} className="mt-2 w-full rounded border p-3" />
      <p className="mt-1 text-sm">Ask the project administrator for access. Your token is not saved by this page.</p></div>
    <button disabled={busy} className="rounded bg-emerald-900 px-5 py-3 text-white disabled:opacity-50">{busy ? "Importing…" : "Import job"}</button>
    {message && <p role="status">{message}</p>}
    {error && <p role="alert" className="text-red-800">{error}</p>}
  </form>;
}
