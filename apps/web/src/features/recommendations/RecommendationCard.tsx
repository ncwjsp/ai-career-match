import Link from "next/link";
import type { Recommendation } from "@/lib/api/client";

function freshness(lastSeenAt: string): string {
  const seen = new Date(lastSeenAt);
  return Number.isNaN(seen.getTime())
    ? "Last check unknown"
    : `Last checked ${seen.toISOString().slice(0, 10)}`;
}

/**
 * One ranked job.
 *
 * The percentage is a fit index computed from semantic similarity and required
 * skill coverage. It is not a probability of being hired, and the card says so
 * rather than leaving a bare number to be misread. Freshness reflects the last
 * manual check of the posting, not continuous monitoring.
 */
export function RecommendationCard({
  candidateId,
  recommendation,
}: {
  candidateId: string;
  recommendation: Recommendation;
}) {
  return (
    <li className="rounded-lg border border-emerald-950/15 bg-white/60 p-5">
      <div className="flex items-baseline justify-between gap-4">
        <span className="text-xs text-emerald-950/60">#{recommendation.rank}</span>
        <span className="text-sm">
          <span className="text-lg font-medium">{recommendation.score.toFixed(1)}%</span>
          <span className="ml-1 text-emerald-950/60">match</span>
        </span>
      </div>
      <h3 className="mt-2 text-lg font-medium">
        <Link
          href={`/recommendations/${encodeURIComponent(candidateId)}/${encodeURIComponent(recommendation.job_id)}?revision=${recommendation.revision}`}
          className="underline-offset-4 hover:underline"
        >
          {recommendation.job_summary ?? recommendation.job_id}
        </Link>
      </h3>
      {recommendation.strengths.length > 0 ? (
        <p className="mt-2 text-sm leading-6 text-emerald-950/70">
          Strengths: {recommendation.strengths.join(", ")}
        </p>
      ) : null}
      {recommendation.gaps.length > 0 ? (
        <p className="mt-1 text-sm leading-6 text-emerald-950/70">
          Not evidenced in your resume: {recommendation.gaps.join(", ")}
        </p>
      ) : null}
      <p className="mt-3 text-xs text-emerald-950/55">
        {freshness(recommendation.last_seen_at)} ·{" "}
        <a href={recommendation.source_url} className="underline" rel="noreferrer noopener">
          Source posting
        </a>
      </p>
    </li>
  );
}
