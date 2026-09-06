import type { components } from "./generated";

export type FixtureBundle = components["schemas"]["FixtureBundle"];
export type CandidateProfile = components["schemas"]["CandidateProfile"];
export type RecommendationSet = components["schemas"]["RecommendationSet"];
export type JobChangeEvent = components["schemas"]["JobChangeEvent"];

export async function loadDevelopmentFixtures(): Promise<FixtureBundle> {
  const response = await fetch("/backend/dev/fixtures", { cache: "no-store" });
  if (!response.ok) throw new Error("Development fixtures could not be loaded.");
  return (await response.json()) as FixtureBundle;
}
