"use client";

import { useParams } from "next/navigation";
import { RecommendationList } from "@/features/recommendations/RecommendationList";

export default function RecommendationsPage() {
  const params = useParams<{ candidateId: string }>();
  const candidateId = params?.candidateId ?? "";
  return (
    <div>
      <h1 className="mb-6 text-2xl font-medium tracking-tight">Recommended jobs</h1>
      {candidateId ? (
        <RecommendationList candidateId={candidateId} />
      ) : (
        <p className="text-sm">No candidate was selected.</p>
      )}
    </div>
  );
}
