import type { components } from "./generated";

export type FixtureBundle = components["schemas"]["FixtureBundle"];
export type CandidateProfile = components["schemas"]["CandidateProfile"];
export type RecommendationSet = components["schemas"]["RecommendationSet"];
export type Recommendation = components["schemas"]["Recommendation"];
export type JobPosting = components["schemas"]["JobPosting"];
export type JobChangeEvent = components["schemas"]["JobChangeEvent"];
export type MatchExplanation = components["schemas"]["MatchExplanation"];
export type SkillComparison = components["schemas"]["SkillComparison"];
export type AnalysisRun = components["schemas"]["AnalysisRun"];
export type ErrorResponse = components["schemas"]["ErrorResponse"];

/**
 * One transport for every backend call.
 *
 * Requests go to the same-origin `/backend/*` proxy, so the session cookie
 * travels as a first-party cookie and no backend URL or credential ever reaches
 * the browser bundle. Errors keep the backend's structured code, because the
 * UI has to distinguish "not implemented yet" from "your session expired".
 */
const BASE = "/backend";

export class ApiError extends Error {
  readonly status: number;
  readonly code: string;
  readonly retryable: boolean;

  constructor(status: number, code: string, message: string, retryable: boolean) {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.code = code;
    this.retryable = retryable;
  }

  /** The owning member has not implemented this route yet. */
  get isPlanned(): boolean {
    return this.status === 501;
  }

  get isForbidden(): boolean {
    return this.status === 403;
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  let response: Response;
  try {
    response = await fetch(BASE + path, {
      ...init,
      cache: "no-store",
      credentials: "same-origin",
      headers: { Accept: "application/json", ...(init?.headers ?? {}) },
    });
  } catch {
    throw new ApiError(0, "NETWORK_ERROR", "The service could not be reached.", true);
  }
  if (!response.ok) {
    throw await toApiError(response);
  }
  return (await response.json()) as T;
}

async function toApiError(response: Response): Promise<ApiError> {
  try {
    const body = (await response.json()) as ErrorResponse;
    return new ApiError(
      response.status,
      body.error.code,
      body.error.message,
      body.error.retryable,
    );
  } catch {
    return new ApiError(response.status, "UNEXPECTED_ERROR", "The request failed.", false);
  }
}

export function loadDevelopmentFixtures(): Promise<FixtureBundle> {
  return request<FixtureBundle>("/dev/fixtures");
}

export function getRecommendations(candidateId: string): Promise<RecommendationSet> {
  return request<RecommendationSet>(
    `/api/v1/candidates/${encodeURIComponent(candidateId)}/recommendations`,
  );
}

export function getAnalysis(analysisId: string): Promise<AnalysisRun> {
  return request<AnalysisRun>(`/api/v1/analyses/${encodeURIComponent(analysisId)}`);
}

export function getJob(jobId: string): Promise<JobPosting> {
  return request<JobPosting>(`/api/v1/jobs/${encodeURIComponent(jobId)}`);
}

function explanationPath(candidateId: string, revision: number, jobId: string): string {
  return (
    `/api/v1/candidates/${encodeURIComponent(candidateId)}` +
    `/recommendations/${revision}/jobs/${encodeURIComponent(jobId)}/explanation`
  );
}

export function getExplanation(
  candidateId: string,
  revision: number,
  jobId: string,
): Promise<MatchExplanation> {
  return request<MatchExplanation>(explanationPath(candidateId, revision, jobId));
}

export function requestExplanation(
  candidateId: string,
  revision: number,
  jobId: string,
): Promise<MatchExplanation> {
  return request<MatchExplanation>(explanationPath(candidateId, revision, jobId), {
    method: "POST",
  });
}
