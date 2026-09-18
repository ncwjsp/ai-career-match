import { AnalysisProgress } from "@/features/upload/ResumeUpload";

export default async function AnalysisPage({ params, searchParams }: {
  params: Promise<{ analysisId: string }>;
  searchParams: Promise<{ resume?: string; candidate?: string }>;
}) {
  const { analysisId } = await params;
  const { resume, candidate } = await searchParams;
  if (!resume || !candidate) return <p>This analysis link is incomplete. Return to the upload page.</p>;
  return <div><h1 className="text-3xl font-medium">Your resume analysis</h1>
    <AnalysisProgress accepted={{ analysis_id: analysisId, resume_id: resume, candidate_id: candidate, status_url: `/api/v1/analyses/${analysisId}` }} />
  </div>;
}
