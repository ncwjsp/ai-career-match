"use client";

import { useParams, useSearchParams } from "next/navigation";
import { JobDetail } from "@/features/job-detail/JobDetail";

export default function JobDetailPage() {
  const params = useParams<{ candidateId: string; jobId: string }>();
  const search = useSearchParams();
  const revision = Number(search.get("revision"));
  if (!params?.candidateId || !params?.jobId) {
    return <p className="text-sm">No job was selected.</p>;
  }
  return (
    <JobDetail
      candidateId={params.candidateId}
      jobId={params.jobId}
      revision={Number.isFinite(revision) && revision > 0 ? revision : null}
    />
  );
}
