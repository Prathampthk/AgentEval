import { test, expect } from "@playwright/test";
test("dataset to run details comparison and honest judge-study status", async ({
  page,
  request,
}) => {
  await page.goto("/dashboard/");
  await expect(
    page.getByRole("heading", { name: "Overview", exact: true }),
  ).toBeVisible();
  await page.getByRole("button", { name: "Runs", exact: true }).click();
  await page
    .getByLabel("Name", { exact: true })
    .fill("Browser smoke " + Date.now());
  await page.getByRole("button", { name: "Save dataset", exact: true }).click();
  await expect(page.getByRole("status")).toHaveText("Dataset saved");
  await expect(
    page.getByLabel("Dataset version", { exact: true }),
  ).not.toHaveValue("");
  const dataset = await page
    .getByLabel("Dataset version", { exact: true })
    .inputValue();
  expect(dataset).toBeTruthy();
  await page.getByRole("button", { name: "Submit run", exact: true }).click();
  await expect(page.getByRole("status")).toHaveText("Submission saved");
  const completed = await request.post("http://127.0.0.1:8010/runs", {
    data: { dataset_id: dataset },
  });
  expect(completed.ok()).toBeTruthy();
  const run = await completed.json();
  await page.getByRole("button", { name: "Refresh", exact: true }).click();
  await page
    .getByRole("button", { name: run.id.slice(0, 8), exact: true })
    .click();
  await expect(page.getByText("Expected:", { exact: false })).toBeVisible();
  await expect(page.getByText("QUALITY PASS", { exact: true })).toBeVisible();
  await page.getByRole("button", { name: "Compare", exact: true }).click();
  await page.getByLabel("Baseline", { exact: true }).selectOption(run.id);
  await page.getByLabel("Candidate", { exact: true }).selectOption(run.id);
  await page.getByRole("button", { name: "Compare runs", exact: true }).click();
  await expect(
    page.getByRole("heading", { name: "PASS", exact: true }),
  ).toBeVisible();
  await page.getByRole("button", { name: "Judge study", exact: true }).click();
  await expect(
    page.getByText("Human labels are pending.", { exact: false }),
  ).toBeVisible();
  await page.getByRole("button", { name: "Overview", exact: true }).click();
  await page.goto("http://127.0.0.1:8010/dashboard/");
  await expect(
    page.getByRole("heading", { name: "Overview", exact: true }),
  ).toBeVisible();
  await expect(
    page.getByText("simulated runs;", { exact: false }),
  ).toBeVisible();
  await page.screenshot({ path: "test-results/dashboard.png", fullPage: true });
});
