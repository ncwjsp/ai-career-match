"use client";

import { useCallback } from "react";
import { EmptyState, ErrorState, LoadingState } from "@/components/ui/states";
import { getRecommendations } from "@/lib/api/client";
import type { RecommendationSet } from "@/lib/api/client";
import { usePolling } from "@/lib/api/usePolling";
import { RecommendationCard } from "./RecommendationCard";

const settled = (value: RecommendationSet) => value.refresh_state !== "pending";

/**
 * The ranked list for one candidate.
 *
 * The list is bound to a published revision, so ranks stay coherent while it is
 * read. New jobs are matched by the worker whether or not this page is open;
 * polling only decides how soon an open tab sees the next revision.
 */
export function RecommendationList({ candidateId }: { candidateId: string }) {
  const load = useCallback(() => getRecommendations(candidateId), [candidateId]);
  const { data, error, loading, refresh } = usePolling(load, { isSettled: settled });

  if (loading && !data) {
    return <LoadingState label="Loading your recommendations…" />;
  }
  if (error && !data) {
    if (error.isPlanned) {
      return (
        <EmptyState
          title="Recommendations are not available yet"
          detail="The ranking API is still being built. Matching, storage and explanations are in place; this page will fill in once the ranked-results endpoint ships."
        />
      );
    }
    if (error.isForbidden) {
      return (
        <EmptyState
          title="This session has ended"
          detail="Recommendations are tied to the session that uploaded the resume. Upload a resume again to start a new one."
        />
      );
    }
    return (
      <ErrorState
        title="Your recommendations could not be loaded"
        detail={error.message}
        onRetry={refresh}
      />
    );
  }
  if (!data) return null;
  if (data.results.length === 0) {
    return (
      <EmptyState
        title="No jobs match yet"
        detail="Nothing in the imported corpus matches this profile so far. New jobs are matched automatically as they are imported, with no need to upload again."
      />
    );
  }

  const updated = new Date(data.updated_at);
  return (
    <section>
      <p className="mb-4 text-sm text-emerald-950/65" aria-live="polite">
        Revision {data.revision} ·{" "}
        {Number.isNaN(updated.getTime()) ? "updated recently" : `updated ${updated.toISOString().slice(0, 16).replace("T", " ")} UTC`}
        {data.refresh_state === "pending" ? " · refreshing with newly imported jobs" : ""}
        {data.refresh_state === "failed" ? " · the last refresh failed and will be retried" : ""}
      </p>
      <ul className="flex flex-col gap-4">
        {data.results.map((recommendation) => (
          <RecommendationCard
            key={recommendation.job_id}
            candidateId={candidateId}
            recommendation={recommendation}
          />
        ))}
      </ul>
      <p className="mt-6 text-xs leading-5 text-emerald-950/55">
        A match percentage describes how well this profile fits the posting&apos;s text and
        required skills. It is not a probability of being hired.
      </p>
    </section>
  );
}
