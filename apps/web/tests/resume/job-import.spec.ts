import { test, expect } from "@playwright/test";

test("team can import and recheck a job, with errors shown", async ({ page }) => {
  let calls = 0;
  await page.route("**/backend/api/v1/job-imports", async route => {
    expect(route.request().headers().authorization).toBe("Bearer synthetic-token");
    calls++;
    if (calls === 3) {
      await route.fulfill({ status: 403, json: { error: { code: "FORBIDDEN", message: "Invalid team token", retryable: false } } });
    } else {
      await route.fulfill({ json: { run_id: "run-1", new_jobs: calls === 1 ? 1 : 0, changed_jobs: 0, unchanged_jobs: calls === 2 ? 1 : 0, event_ids: [], warnings: [] } });
    }
  });
  await page.goto("/job-import");
  await page.getByLabel("Job URL").fill("https://job-boards.greenhouse.io/example/jobs/123");
  await page.getByLabel("Team access token").fill("synthetic-token");
  await page.getByRole("button", { name: "Import job", exact: true }).click();
  await expect(page.getByRole("status")).toContainText("Job added");
  await page.getByRole("button", { name: "Import job", exact: true }).click();
  await expect(page.getByRole("status")).toContainText("already up to date");
  await page.getByRole("button", { name: "Import job", exact: true }).click();
  await expect(page.getByRole("alert").filter({ hasText: "Invalid team token" })).toContainText("Invalid team token");
  await page.reload();
  await expect(page.getByLabel("Team access token")).toHaveValue("");
});
