import { expect, test } from "@playwright/test";
import fixtures from "../../../../contracts/examples/bootstrap.json";

const accepted = { candidate_id: "candidate-demo", resume_id: "resume-demo", analysis_id: "analysis-demo", status_url: "/api/v1/analyses/analysis-demo" };
const run = { ...accepted, state: "ready", created_at: "2026-09-17T00:00:00Z", updated_at: "2026-09-17T00:00:00Z", warnings: [], error: null, result_count: 0, corpus_snapshot: "synthetic" };

test("single upload, progress, profile evidence and reload", async ({ page }) => {
  let ready = false;
  await page.route("**/backend/api/v1/resumes", async route => {
    expect(route.request().postDataBuffer()?.toString()).toContain("synthetic.pdf");
    await route.fulfill({ json: accepted, status: 202 });
  });
  await page.route("**/backend/api/v1/analyses/*", route => route.fulfill({ json: { ...run, state: ready ? "ready" : "profiling" } }));
  await page.route("**/backend/api/v1/resumes/*/profile", route => route.fulfill({ json: fixtures.profiles[0] }));
  await page.goto("/");
  await page.getByLabel("Resume file").setInputFiles({ name: "synthetic.pdf", mimeType: "application/pdf", buffer: Buffer.from("synthetic") });
  await page.getByRole("button", { name: "Analyze resume" }).click();
  await expect(page.getByRole("status")).toContainText("Recognizing");
  ready = true;
  await expect(page.getByRole("link", { name: "View matching jobs" })).toBeVisible();
  await expect(page.getByRole("heading", { name: "Your recognized profile" })).toBeVisible();
  await page.getByText("Source evidence", { exact: true }).click();
  await expect(page.locator("q").first()).toBeVisible();
  await page.reload();
  await expect(page.getByRole("heading", { name: "Your resume analysis" })).toBeVisible();
  await expect(page.getByRole("link", { name: "View matching jobs" })).toBeVisible();
});

test("upload failure can be retried without losing selected file", async ({ page }) => {
  let attempts = 0;
  await page.route("**/backend/api/v1/resumes", route => route.fulfill(attempts++ ? { json: accepted, status: 202 } : { json: { error: { code: "DEPENDENCY_UNAVAILABLE", message: "Storage is unavailable. Try again.", retryable: true } }, status: 503 }));
  await page.route("**/backend/api/v1/analyses/*", route => route.fulfill({ json: { ...run, state: "failed", error: { message: "No readable text was found." } } }));
  await page.goto("/");
  await page.getByLabel("Resume file").setInputFiles({ name: "synthetic.pdf", mimeType: "application/pdf", buffer: Buffer.from("synthetic") });
  await page.getByRole("button", { name: "Analyze resume" }).click();
  await expect(page.getByRole("alert").filter({ hasText: "Upload unsuccessful" })).toContainText("Upload unsuccessful");
  await page.getByRole("button", { name: "Analyze resume" }).click();
  await expect(page.getByText("No readable text was found.")).toBeVisible();
  await expect(page.getByRole("link", { name: "View matching jobs" })).toHaveCount(0);
});

test("unsupported file stays on the form with an accessible error", async ({ page }) => {
  await page.goto("/");
  await page.getByLabel("Resume file").setInputFiles({ name: "synthetic.txt", mimeType: "text/plain", buffer: Buffer.from("synthetic") });
  await page.getByRole("button", { name: "Analyze resume" }).click();
  await expect(page.getByRole("alert").filter({ hasText: "Upload unsuccessful" })).toContainText("Upload unsuccessful");
  await expect(page.getByText("Choose a nonempty PDF or DOCX file up to 10 MB.")).toBeVisible();
});
