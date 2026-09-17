"use client";

import Link from "next/link";
import { useCallback, useState } from "react";
import { ErrorState, LoadingState } from "@/components/ui/states";
import { getAnalysis, getProfile, uploadResume } from "@/lib/api/client";
import type { AnalysisRun, UploadAccepted } from "@/lib/api/client";
import { usePolling } from "@/lib/api/usePolling";
import { ProfileView } from "@/features/profile/ProfileView";

const profileSettled = () => true;
const settled = (run: AnalysisRun) => run.state === "ready" || run.state === "failed";
const labels: Record<AnalysisRun["state"], string> = {
  queued: "Waiting for processing…", extracting: "Reading your resume…",
  profiling: "Recognizing your experience and skills…", matching: "Finding relevant jobs…",
  ready: "Your results are ready.", failed: "Your resume could not be processed.",
};

export function AnalysisProgress({ accepted }: { accepted: UploadAccepted }) {
  const load = useCallback(() => getAnalysis(accepted.analysis_id), [accepted.analysis_id]);
  const poll = usePolling(load, { intervalMs: 2000, isSettled: settled });
  const loadProfile = useCallback(() => getProfile(accepted.resume_id), [accepted.resume_id]);
  const profile = usePolling(loadProfile, {
    enabled: poll.data?.state === "matching" || poll.data?.state === "ready",
    isSettled: profileSettled,
  });
  if (poll.error) return <ErrorState title="Unable to check progress" detail={poll.error.message} onRetry={poll.refresh} />;
  if (!poll.data) return <LoadingState label="Loading your analysis…" />;
  const run = poll.data;
  return <div className="mt-6">
    <p role="status" aria-live="polite">{labels[run.state]}</p>
    {run.state === "failed" && <ErrorState title="Processing stopped" detail={run.error?.message ?? "Please try another file."} />}
    {run.state !== "ready" && run.state !== "failed" && <p className="mt-2 text-sm">Processing continues if you leave this page. Keep this browser session to return to your results.</p>}
    {run.state === "ready" && <Link className="mt-4 inline-block rounded bg-emerald-900 px-5 py-3 text-white" href={`/recommendations/${accepted.candidate_id}`}>View matching jobs</Link>}
    {profile.error && <ErrorState title="Profile unavailable" detail={profile.error.message} onRetry={profile.refresh} />}
    {profile.data && <ProfileView profile={profile.data} />}
  </div>;
}

export function ResumeUpload() {
  const [file, setFile] = useState<File | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [accepted, setAccepted] = useState<UploadAccepted | null>(null);
  async function submit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!file) { setError("Choose one PDF or DOCX file."); return; }
    if (!/\.(pdf|docx)$/i.test(file.name) || !file.size || file.size > 10 * 1024 * 1024) {
      setError("Choose a nonempty PDF or DOCX file up to 10 MB."); return;
    }
    setBusy(true); setError(null);
    try {
      const result = await uploadResume(file);
      setAccepted(result);
      window.history.replaceState(null, "", `/analysis/${encodeURIComponent(result.analysis_id)}?resume=${encodeURIComponent(result.resume_id)}&candidate=${encodeURIComponent(result.candidate_id)}`);
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Upload failed. Please try again.");
    } finally { setBusy(false); }
  }
  return <section className="mt-10 max-w-2xl rounded-xl border border-emerald-950/15 bg-white/60 p-6">
    <h2 className="text-xl font-medium">Start with your resume</h2>
    <p id="upload-help" className="mt-2 text-sm leading-6">English PDF or DOCX, up to 10 MB. Use selectable text; scanned images are not supported. Your resume is retained for analysis and matching against newly imported jobs.</p>
    <form onSubmit={submit} className="mt-5 space-y-4" aria-busy={busy}>
      <label className="block text-sm font-semibold" htmlFor="resume-file">Resume file</label>
      <input id="resume-file" type="file" accept=".pdf,.docx" aria-describedby="upload-help" disabled={busy} onChange={e => { setFile(e.target.files?.[0] ?? null); setError(null); }} className="block w-full rounded border border-emerald-950/25 p-3 text-sm" />
      <button disabled={busy} className="rounded bg-emerald-900 px-5 py-3 text-white disabled:opacity-50">{busy ? "Uploading…" : "Analyze resume"}</button>
    </form>
    {error && <div className="mt-4"><ErrorState title="Upload unsuccessful" detail={error} /></div>}
    {accepted && <AnalysisProgress key={accepted.analysis_id} accepted={accepted} />}
  </section>;
}
