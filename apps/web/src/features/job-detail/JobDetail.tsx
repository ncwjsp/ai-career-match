"use client";

import { useCallback } from "react";
import Link from "next/link";
import { SkillState } from "@/components/ui/SkillState";
import { EmptyState, ErrorState, LoadingState, Panel } from "@/components/ui/states";
import { getRecommendations } from "@/lib/api/client";
import { usePolling } from "@/lib/api/usePolling";
import { ExplanationPanel } from "./ExplanationPanel";

/**
 * One selected job: score, required-skill states and the explanation.
 *
 * The detail is read from the published revision the reader came from, so the
 * score and skill states on this page are exactly the ones that produced the
 * rank they clicked.
 */
export function JobDetail({
  candidateId,
  jobId,
  revision,
}: {
  candidateId: string;
  jobId: string;
  revision: number | null;
}) {
  const load = useCallback(() => getRecommendations(candidateId), [candidateId]);
  const { data, error, loading, refresh } = usePolling(load, { intervalMs: 15000 });

  if (loading && !data) return <LoadingState label="Loading this job…" />;
  if (error && !data) {
    if (error.isPlanned) {
      return (
        <EmptyState
          title="Job detail is not available yet"
          detail="The ranked-results endpoint is still being built, so there is nothing to show for this job."
        />
      );
    }
    return <ErrorState title="This job could not be loaded" detail={error.message} onRetry={refresh} />;
  }

  const entry = data?.results.find((result) => result.job_id === jobId);
  if (!entry || !data) {
    return (
      <EmptyState
        title="This job is no longer in your results"
        detail="The posting may have expired or been closed since this page was opened. Expired postings are removed from recommendations."
      />
    );
  }

  return (
    <article className="flex flex-col gap-5">
      <Panel>
        <p className="text-sm text-emerald-950/60">Rank #{entry.rank}</p>
        <h1 className="mt-1 text-2xl font-medium">{entry.job_summary ?? entry.job_id}</h1>
        <p className="mt-2 text-lg">
          {entry.score.toFixed(1)}% <span className="text-sm text-emerald-950/60">match</span>
        </p>
        <p className="mt-2 text-xs text-emerald-950/55">
          Scored with {entry.scoring_version} from revision {entry.revision} ·{" "}
          <a href={entry.source_url} className="underline" rel="noreferrer noopener">
            Source posting
          </a>
        </p>
      </Panel>

      <Panel>
        <h2 className="font-medium">Required skills</h2>
        <ul className="mt-3 flex flex-col gap-2">
          {entry.skill_comparison.map((skill) => (
            <SkillState key={skill.skill} skill={skill} />
          ))}
        </ul>
        <p className="mt-3 text-xs leading-5 text-emerald-950/55">
          &ldquo;Not evidenced&rdquo; means this resume did not show the skill. It is not a
          statement that you lack it.
        </p>
      </Panel>

      <ExplanationPanel
        candidateId={candidateId}
        revision={revision ?? entry.revision}
        jobId={jobId}
      />

      <Link
        href={`/recommendations/${encodeURIComponent(candidateId)}`}
        className="text-sm underline underline-offset-4"
      >
        Back to all recommendations
      </Link>
    </article>
  );
}
