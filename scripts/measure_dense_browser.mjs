import { chromium } from "../frontend/node_modules/playwright/index.mjs";
import fs from "node:fs/promises";
import { performance } from "node:perf_hooks";
import { createHash } from "node:crypto";
import { execFileSync } from "node:child_process";
import path from "node:path";
const [directory, output, api = "http://127.0.0.1:8001", frontend = "http://127.0.0.1:5173"] =
  process.argv.slice(2);
if (!directory || !output)
  throw new Error(
    "Usage:node scripts/measure_dense_browser.mjs PRIVATE_FIXTURE NEW_REPORT [API] [FRONTEND]",
  );
for (const input of [api, frontend]) {
  const u = new URL(input);
  if (
    u.protocol !== "http:" ||
    !["127.0.0.1", "localhost"].includes(u.hostname) ||
    u.pathname !== "/"
  )
    throw new Error("Only loopback HTTP services are supported");
}
try {
  await fs.access(output);
  throw new Error("Report already exists");
} catch (e) {
  if (e.code !== "ENOENT") throw e;
}
const workers = JSON.parse(await fs.readFile(path.join(directory, "report.json"), "utf8"));
if (
  workers.schema_version !== "windows-worker-baseline-v1" ||
  workers.production_ready !== false ||
  workers.data_origin !== "synthetic-control" ||
  workers.density_control !== "all-events-share-one-device" ||
  workers.samples.length !== 3
)
  throw new Error("Complete synthetic shared-device fixture required");
const python = process.platform === "win32" ? ".venv/Scripts/python.exe" : ".venv/bin/python";
const targets = JSON.parse(
  execFileSync(
    python,
    [
      "-c",
      `import sqlite3,sys,json
db=sqlite3.connect('file:'+sys.argv[1]+'/fixture.db?mode=ro',uri=True)
rows=db.execute("select r.id,r.investigation_id,r.result_checksum,r.status,i.owner_id from analysis_runs r join investigations i on i.id=r.investigation_id order by r.created_at").fetchall()
assert len(rows)==3 and all(status=='completed' and owner=='synthetic-capacity-only' for _,_,_,status,owner in rows)
print(json.dumps([dict(run=r,case=c,checksum=h) for r,c,h,_,_ in rows]))
db.close()`,
      path.resolve(directory),
    ],
    { encoding: "utf8" },
  ),
);
targets.forEach((target, index) => {
  if (target.checksum !== workers.samples[index].result_sha256)
    throw new Error("Fixture/report checksum mismatch");
});
const browser = await chromium.launch({ headless: true });
const report = {
  schema_version: "dense-browser-baseline-v1",
  production_ready: false,
  data_origin: "synthetic-control",
  worker_source_commit: workers.source_commit,
  frontend_source_commit: execFileSync("git", ["rev-parse", "HEAD"], { encoding: "utf8" }).trim(),
  scope:
    "Local production frontend + isolated real API/SQLite/storage. Playwright HTTP relay injects the synthetic development owner; relay overhead included. No hosted authentication/capacity claim.",
  samples: [],
};
report.frontend_graph_source_sha256 = createHash("sha256")
  .update(await fs.readFile("frontend/components/evidence-graph.tsx"))
  .digest("hex");
report.measurement_driver_sha256 = createHash("sha256")
  .update(await fs.readFile("scripts/measure_dense_browser.mjs"))
  .digest("hex");
try {
  for (const [index, target] of targets.entries()) {
    const context = await browser.newContext({ viewport: { width: 1440, height: 1050 } });
    const page = await context.newPage();
    const errors = [];
    const failures = [];
    let bytes = 0,
      requests = 0;
    page.on("pageerror", (e) => errors.push(e.name));
    await page.addInitScript(() => {
      window.__longTasks = [];
      new PerformanceObserver((list) =>
        window.__longTasks.push(
          ...list.getEntries().map((e) => ({ start: e.startTime, duration: e.duration })),
        ),
      ).observe({ type: "longtask", buffered: true });
    });
    await page.route("**/api/v1/**", async (route) => {
      const url = new URL(route.request().url());
      const response = await route.fetch({
        url: api + url.pathname + url.search,
        headers: { ...route.request().headers(), "X-Development-User": "synthetic-capacity-only" },
        timeout: 60000,
      });
      requests++;
      bytes += (await response.body()).length;
      if (response.status() >= 400) failures.push(response.status());
      await route.fulfill({ response });
    });
    const cdp = await context.newCDPSession(page);
    await cdp.send("Performance.enable");
    const heap = async () =>
      (await cdp.send("Performance.getMetrics")).metrics.find((x) => x.name === "JSHeapUsedSize")
        .value;
    const start = performance.now();
    await page.goto(`${frontend}/investigations/${target.case}?run=${target.run}&view=evidence`);
    await page
      .getByRole("heading", { name: "Persisted findings", exact: true })
      .waitFor({ timeout: 60000 });
    await page.getByRole("tab", { name: "Evidence", exact: true }).waitFor();
    const evidenceMs = performance.now() - start;
    const evidenceHeap = await heap();
    const networkStart = performance.now();
    const graphStageStart = await page.evaluate(() => performance.now());
    await page.getByRole("tab", { name: "Network", exact: true }).click();
    await page.locator(".evidence-canvas canvas").first().waitFor({ timeout: 60000 });
    await page.getByRole("button", { name: "Fit graph", exact: true }).click({ timeout: 60000 });
    await page.evaluate(
      () => new Promise((resolve) => requestAnimationFrame(() => requestAnimationFrame(resolve))),
    );
    const networkMs = performance.now() - networkStart;
    const graphStageEnd = await page.evaluate(() => performance.now());
    const scope = await page.locator(".network-scope").textContent();
    const counts = scope.match(/([\d,]+) entities · ([\d,]+) explicit links/);
    const networkHeap = await heap();
    const pickerStageStart = await page.evaluate(() => performance.now());
    await page.getByRole("combobox", { name: "Entity", exact: true }).click();
    await page.getByRole("listbox").getByRole("option").first().click();
    await page.locator(".selection-details").waitFor();
    const pickerStageEnd = await page.evaluate(() => performance.now());
    await page.getByRole("tab", { name: "Evidence", exact: true }).click();
    const metrics = await page.evaluate(
      ({ graphStageStart, graphStageEnd, pickerStageStart, pickerStageEnd }) => ({
        max_long_task_ms: Math.max(0, ...window.__longTasks.map((e) => e.duration)),
        graph_stage_max_long_task_ms: Math.max(
          0,
          ...window.__longTasks
            .filter((e) => e.start >= graphStageStart && e.start < graphStageEnd)
            .map((e) => e.duration),
        ),
        entity_picker_max_long_task_ms: Math.max(
          0,
          ...window.__longTasks
            .filter((e) => e.start >= pickerStageStart && e.start < pickerStageEnd)
            .map((e) => e.duration),
        ),
        long_tasks: window.__longTasks.length,
        no_horizontal_overflow: document.documentElement.scrollWidth <= window.innerWidth,
      }),
      { graphStageStart, graphStageEnd, pickerStageStart, pickerStageEnd },
    );
    report.samples.push({
      events: workers.samples[index].events,
      result_sha256: workers.samples[index].result_sha256,
      evidence_ready_ms: evidenceMs,
      network_ready_and_fit_ms: networkMs,
      evidence_js_heap_bytes: evidenceHeap,
      network_js_heap_bytes: networkHeap,
      graph_entities: Number(counts[1].replaceAll(",", "")),
      graph_links: Number(counts[2].replaceAll(",", "")),
      api_response_body_bytes: bytes,
      api_requests: requests,
      page_error_count: errors.length,
      http_error_statuses: failures,
      entity_selection_and_return_to_evidence: true,
      ...metrics,
    });
    await context.close();
    console.log(JSON.stringify(report.samples.at(-1)));
  }
  await fs.writeFile(output, JSON.stringify(report, null, 2) + "\n", { flag: "wx" });
} finally {
  await browser.close();
}
