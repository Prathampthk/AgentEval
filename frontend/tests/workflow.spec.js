import { test, expect } from "@playwright/test";
test("dataset to run details comparison and honest judge-study status", async ({
  page,
  request,
}) => {
  const ready = await request.get("/health/ready");
  expect(ready.ok()).toBeTruthy();
  expect(await ready.json()).toMatchObject({
    provider: "fake",
    simulated: true,
    database: "ready",
  });
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
  const submitted = page.waitForResponse(
    (response) =>
      new URL(response.url()).pathname === "/queued-runs" &&
      response.request().method() === "POST",
  );
  await page.getByRole("button", { name: "Submit run", exact: true }).click();
  await expect(page.getByRole("status")).toHaveText("Submission saved");
  const submission = await submitted;
  expect(submission.ok()).toBeTruthy();
  const queued = await submission.json();
  let run;
  if (process.env.AGENTEVAL_E2E_URL) {
    await expect
      .poll(async () => {
        const response = await request.get("/runs/" + queued.id);
        expect(response.ok()).toBeTruthy();
        run = await response.json();
        return run.status;
      })
      .toBe("COMPLETED");
    expect(run.simulated).toBe(true);
    const jobs = await request.get("/runs/" + queued.id + "/jobs");
    expect(jobs.ok()).toBeTruthy();
    expect(await jobs.json()).toMatchObject([
      { status: "COMPLETED", attempts: 1 },
    ]);
  } else {
    const completed = await request.post("/runs", {
      data: { dataset_id: dataset },
    });
    expect(completed.ok()).toBeTruthy();
    run = await completed.json();
  }
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
    page.getByText("Judge predictions are pending.", { exact: true }),
  ).toBeVisible();
  await expect(
    page
      .locator("article")
      .filter({ hasText: "Human labels" })
      .locator("strong"),
  ).toHaveText("50");
  await page.getByRole("button", { name: "Overview", exact: true }).click();
  await page.goto("/dashboard/");
  await expect(
    page.getByRole("heading", { name: "Overview", exact: true }),
  ).toBeVisible();
  await expect(
    page.getByText("simulated runs;", { exact: false }),
  ).toBeVisible();
  await page.screenshot({ path: "test-results/dashboard.png", fullPage: true });
});
