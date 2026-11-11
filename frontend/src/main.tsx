import React, { useEffect, useRef, useState } from "react";
import { createRoot } from "react-dom/client";
import "./style.css";
type DataSet = {
  id: string;
  name: string;
  version: string;
  case_count: number;
};
type Case = { external_id: string; question: string; expected_answer: string };
type Result = {
  test_case_id: string;
  answer: string;
  passed: boolean;
  judgment: {
    correctness: number;
    relevance: number;
    groundedness: number | null;
    explanation: string;
  };
};
type Run = {
  id: string;
  status: string;
  model: string;
  simulated: boolean;
  results: Result[];
  error_category: string | null;
};
type Job = {
  id: string;
  status: string;
  attempts: number;
  max_attempts: number;
  last_error: string | null;
};
type Overview = {
  simulated_runs: number;
  latest_run: { id: string; status: string } | null;
  total_runs: number;
  result_count: number;
  passed: number;
  failed_quality: number;
  average_correctness: number | null;
  average_relevance: number | null;
  average_groundedness: number | null;
  average_latency_ms: number | null;
  jobs: Record<string, number>;
};
type Study = {
  status: string;
  human_labeled: number;
  paired_count: number;
  simulated_judge?: boolean | null;
  judge_prompt_version?: string | null;
  scope?: string;
  agreement: number | null;
  precision: number | null;
  recall: number | null;
  confusion_matrix: Record<string, number>;
  disagreements: { example_id: string; category: string }[];
};
function studySummary(study: Study | null) {
  if (!study) return "Loading study results…";
  if (study.paired_count) {
    return study.simulated_judge
      ? "Analysis of paired human and simulated judge decisions."
      : "Analysis of paired human and judge decisions.";
  }
  return study.human_labeled
    ? "Judge predictions are pending."
    : "Human labels are pending.";
}
type Comparison = {
  outcome: string;
  reasons: string[];
  paired_cases: number;
  metrics: Record<string, number>;
};
const initialCases = JSON.stringify(
  [
    {
      external_id: "capital",
      question: "What is the capital of France?",
      expected_answer: "Paris",
      context: "Paris",
      exact_match: true,
    },
  ],
  null,
  2,
);
async function api<T>(
  path: string,
  body?: unknown,
  key?: string,
  signal?: AbortSignal,
): Promise<T> {
  const response = await fetch(path, {
    method: body === undefined ? "GET" : "POST",
    headers: {
      "Content-Type": "application/json",
      ...(key ? { "Idempotency-Key": key } : {}),
    },
    body: body === undefined ? undefined : JSON.stringify(body),
    signal,
  });
  const data = await response.json();
  if (!response.ok)
    throw Error(
      typeof data.detail === "string"
        ? data.detail
        : JSON.stringify(data.detail),
    );
  return data;
}
const number = (value: number | null | undefined, suffix = "") =>
  value == null ? "—" : value.toFixed(2) + suffix;
function App() {
  const [view, setView] = useState("Overview"),
    [datasets, setDatasets] = useState<DataSet[]>([]),
    [dataset, setDataset] = useState(""),
    [cases, setCases] = useState<Case[]>([]),
    [runs, setRuns] = useState<Run[]>([]),
    [selected, setSelected] = useState(""),
    [details, setDetails] = useState<Run | null>(null),
    [jobs, setJobs] = useState<Job[]>([]),
    [overview, setOverview] = useState<Overview | null>(null),
    [study, setStudy] = useState<Study | null>(null),
    [error, setError] = useState(""),
    [notice, setNotice] = useState(""),
    [busy, setBusy] = useState(false),
    [tick, setTick] = useState(0);
  const [name, setName] = useState("Demo facts"),
    [version, setVersion] = useState("1"),
    [caseText, setCaseText] = useState(initialCases),
    [prompt, setPrompt] = useState(
      "Answer the question using the supplied context.",
    ),
    [baseline, setBaseline] = useState(""),
    [candidate, setCandidate] = useState(""),
    [comparison, setComparison] = useState<Comparison | null>(null);
  const pending = useRef<{ body: string; key: string } | null>(null);
  useEffect(() => {
    const controller = new AbortController();
    let timer: ReturnType<typeof setTimeout>;
    let alive = true;
    async function refresh() {
      try {
        const [ds, ov, st] = await Promise.all([
          api<DataSet[]>("/datasets", undefined, undefined, controller.signal),
          api<Overview>("/overview", undefined, undefined, controller.signal),
          api<Study>(
            "/judge-validation",
            undefined,
            undefined,
            controller.signal,
          ),
        ]);
        if (!alive) return;
        setDatasets(ds);
        setOverview(ov);
        setStudy(st);
        if (!dataset && ds.length) setDataset(ds[0].id);
        if (dataset) {
          const [r, d] = await Promise.all([
            api<Run[]>(
              "/runs?dataset_id=" + dataset,
              undefined,
              undefined,
              controller.signal,
            ),
            api<{ cases: Case[] }>(
              "/datasets/" + dataset,
              undefined,
              undefined,
              controller.signal,
            ),
          ]);
          if (!alive) return;
          setRuns(r);
          setCases(d.cases);
          if (selected) {
            const [detail, j] = await Promise.all([
              api<Run>(
                "/runs/" + selected,
                undefined,
                undefined,
                controller.signal,
              ),
              api<Job[]>(
                "/runs/" + selected + "/jobs",
                undefined,
                undefined,
                controller.signal,
              ),
            ]);
            if (!alive) return;
            setDetails(detail);
            setJobs(j);
          }
        }
      } catch (e) {
        if (alive) setError(String(e));
      } finally {
        if (alive) timer = setTimeout(refresh, 5000);
      }
    }
    void refresh();
    return () => {
      alive = false;
      controller.abort();
      clearTimeout(timer);
    };
  }, [dataset, selected, tick]);
  async function action(work: () => Promise<void>) {
    setBusy(true);
    setError("");
    setNotice("");
    try {
      await work();
      setTick((t) => t + 1);
    } catch (e) {
      setError(String(e));
    } finally {
      setBusy(false);
    }
  }
  function choose(id: string) {
    setDataset(id);
    setSelected("");
    setDetails(null);
    setJobs([]);
    setBaseline("");
    setCandidate("");
    setComparison(null);
  }
  const selectDataset = (
    <label>
      Dataset version
      <select
        aria-label="Dataset version"
        value={dataset}
        onChange={(e) => choose(e.target.value)}
      >
        <option value="">Choose a dataset</option>
        {datasets.map((d) => (
          <option key={d.id} value={d.id}>
            {d.name} · v{d.version} · {d.case_count} cases
          </option>
        ))}
      </select>
    </label>
  );
  return (
    <div className="shell">
      <aside>
        <div className="brand">
          A<span>AgentEval</span>
        </div>
        <p className="aside-note">Evaluation workspace</p>
        <nav>
          {["Overview", "Runs", "Compare", "Judge study"].map((item) => (
            <button
              key={item}
              className={view === item ? "active" : ""}
              onClick={() => setView(item)}
            >
              {item}
            </button>
          ))}
        </nav>
        <div className="aside-bottom">
          Local evaluation platform
          <br />
          <small>Metrics reflect stored evidence.</small>
        </div>
      </aside>
      <main>
        <header>
          <div>
            <p className="eyebrow">AI QUALITY / REGRESSION TESTING</p>
            <h1>{view}</h1>
          </div>
          <button className="secondary" onClick={() => setTick((t) => t + 1)}>
            Refresh
          </button>
        </header>
        {error && (
          <div role="alert" className="alert">
            {error}
          </div>
        )}
        {notice && (
          <div role="status" className="notice">
            {notice}
          </div>
        )}
        {view === "Overview" && (
          <>
            {!!overview?.simulated_runs && (
              <p className="notice">
                Aggregate includes {overview.simulated_runs} simulated runs;
                these are not live-model performance evidence.
              </p>
            )}
            <p className="intro">
              Understand your evaluations before deciding what to ship.
            </p>
            <div className="stats">
              {[
                ["Evaluation runs", overview?.total_runs],
                ["Accepted results", overview?.result_count],
                ["Quality passes", overview?.passed],
                [
                  "Average latency",
                  number(overview?.average_latency_ms, " ms"),
                ],
              ].map(([title, value]) => (
                <article key={String(title)}>
                  <span>{title}</span>
                  <strong>{value ?? "—"}</strong>
                </article>
              ))}
            </div>
            <div className="columns">
              <section>
                <h2>Quality summary</h2>
                <p>
                  {overview?.passed ?? 0} passed ·{" "}
                  {overview?.failed_quality ?? 0} did not pass
                </p>
                <p>Average rubric scores, on a scale from 0 to 2.</p>
                {[
                  ["Correctness", overview?.average_correctness],
                  ["Relevance", overview?.average_relevance],
                  ["Groundedness", overview?.average_groundedness],
                ].map(([title, value]) => (
                  <div className="metric" key={String(title)}>
                    <span>{title}</span>
                    <meter
                      min="0"
                      max="2"
                      value={typeof value === "number" ? value : 0}
                    />
                    <b>{number(value as number | null | undefined)}</b>
                  </div>
                ))}
                <p className="muted">
                  Missing scores are shown as —. Judge scores are not calibrated
                  probabilities.
                </p>
              </section>
              <section>
                <h2>Job monitoring</h2>
                {overview?.latest_run && (
                  <p>
                    Latest run:{" "}
                    <span
                      className={
                        "badge " + overview.latest_run.status.toLowerCase()
                      }
                    >
                      {overview.latest_run.status}
                    </span>
                  </p>
                )}
                <table>
                  <thead>
                    <tr>
                      <th>State</th>
                      <th>Jobs</th>
                    </tr>
                  </thead>
                  <tbody>
                    {[
                      "PENDING",
                      "RUNNING",
                      "COMPLETED",
                      "FAILED",
                      "CANCELED",
                    ].map((status) => (
                      <tr key={status}>
                        <td>
                          <span className={"badge " + status.toLowerCase()}>
                            {status}
                          </span>
                        </td>
                        <td>{overview?.jobs[status] ?? 0}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </section>
            </div>
            <section>
              <h2>Start an evaluation</h2>
              <p>
                Create a versioned dataset, submit a run, and inspect individual
                answers before comparing versions.
              </p>
              <button onClick={() => setView("Runs")}>Open runs</button>
            </section>
          </>
        )}
        {view === "Runs" && (
          <>
            <div className="columns">
              <section>
                <h2>Create a dataset</h2>
                <label>
                  Name
                  <input
                    value={name}
                    onChange={(e) => setName(e.target.value)}
                  />
                </label>
                <label>
                  Version
                  <input
                    value={version}
                    onChange={(e) => setVersion(e.target.value)}
                  />
                </label>
                <label>
                  Test cases (JSON)
                  <textarea
                    aria-label="Test cases JSON"
                    rows={9}
                    value={caseText}
                    onChange={(e) => setCaseText(e.target.value)}
                  />
                </label>
                <button
                  disabled={busy}
                  onClick={() =>
                    action(async () => {
                      const result = await api<DataSet>("/datasets", {
                        name,
                        version,
                        cases: JSON.parse(caseText),
                      });
                      setDatasets((current) => [
                        { ...result, case_count: JSON.parse(caseText).length },
                        ...current.filter((entry) => entry.id !== result.id),
                      ]);
                      choose(result.id);
                      setNotice("Dataset saved");
                    })
                  }
                >
                  Save dataset
                </button>
              </section>
              <section>
                <h2>Submit evaluation</h2>
                {selectDataset}
                <label>
                  Prompt
                  <textarea
                    value={prompt}
                    rows={4}
                    onChange={(e) => setPrompt(e.target.value)}
                  />
                </label>
                <p className="muted">
                  The selected provider runs on the server. A saved submission
                  may wait for a worker.
                </p>
                <button
                  disabled={busy || !dataset}
                  onClick={() =>
                    action(async () => {
                      const body = { dataset_id: dataset, prompt };
                      const serialized = JSON.stringify(body);
                      if (pending.current?.body !== serialized)
                        pending.current = {
                          body: serialized,
                          key: crypto.randomUUID(),
                        };
                      const result = await api<Run>(
                        "/queued-runs",
                        body,
                        pending.current.key,
                      );
                      pending.current = null;
                      setSelected(result.id);
                      setNotice("Submission saved");
                    })
                  }
                >
                  Submit run
                </button>
              </section>
            </div>
            <section>
              <h2>Evaluation history</h2>
              <div className="scroll">
                <table>
                  <thead>
                    <tr>
                      <th>Run</th>
                      <th>Status</th>
                      <th>Model</th>
                      <th>Source</th>
                      <th>Results</th>
                    </tr>
                  </thead>
                  <tbody>
                    {runs.map((run) => (
                      <tr key={run.id}>
                        <td>
                          <button
                            className="text-button"
                            onClick={() => setSelected(run.id)}
                          >
                            {run.id.slice(0, 8)}
                          </button>
                        </td>
                        <td>
                          <span className={"badge " + run.status.toLowerCase()}>
                            {run.status}
                          </span>
                        </td>
                        <td>{run.model}</td>
                        <td>{run.simulated ? "Simulated" : "Live provider"}</td>
                        <td>{run.results.length}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
                {!runs.length && (
                  <p className="muted">No runs for this dataset yet.</p>
                )}
              </div>
            </section>
            {details && (
              <section>
                <h2>Evaluation details · {details.id.slice(0, 8)}</h2>
                {details.simulated && (
                  <p className="notice">
                    Simulated provider output — not live Gemini quality
                    evidence.
                  </p>
                )}
                {details.error_category && (
                  <p className="alert">Execution: {details.error_category}</p>
                )}
                {details.status === "RUNNING" && (
                  <button
                    className="secondary"
                    disabled={busy}
                    onClick={() =>
                      action(async () => {
                        await api("/runs/" + details.id + "/cancel", {});
                        setNotice("Cancellation requested");
                      })
                    }
                  >
                    Cancel run
                  </button>
                )}
                <table>
                  <thead>
                    <tr>
                      <th>Job</th>
                      <th>Status</th>
                      <th>Attempts</th>
                      <th>Last error</th>
                    </tr>
                  </thead>
                  <tbody>
                    {jobs.map((job) => (
                      <tr key={job.id}>
                        <td>{job.id.slice(0, 8)}</td>
                        <td>{job.status}</td>
                        <td>
                          {job.attempts}/{job.max_attempts}
                        </td>
                        <td>{job.last_error ?? "—"}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
                {details.results.map((result) => (
                  <article className="answer" key={result.test_case_id}>
                    <h3>
                      {cases.find((c) => c.external_id === result.test_case_id)
                        ?.question ?? result.test_case_id}
                    </h3>
                    <p>
                      <b>Expected:</b>{" "}
                      {cases.find((c) => c.external_id === result.test_case_id)
                        ?.expected_answer ?? "—"}
                    </p>
                    <p>
                      <b>Answer:</b> {result.answer}
                    </p>
                    <p>
                      <span
                        className={
                          "badge " + (result.passed ? "completed" : "failed")
                        }
                      >
                        {result.passed ? "QUALITY PASS" : "QUALITY FAIL"}
                      </span>{" "}
                      · correctness {result.judgment.correctness}/2 · relevance{" "}
                      {result.judgment.relevance}/2 · groundedness{" "}
                      {result.judgment.groundedness ?? "—"}
                    </p>
                    <p>{result.judgment.explanation}</p>
                  </article>
                ))}
                {!details.results.length && (
                  <p className="muted">No accepted results yet.</p>
                )}
              </section>
            )}
          </>
        )}
        {view === "Compare" && (
          <section>
            <h2>Compare run versions</h2>
            {selectDataset}
            <div className="columns">
              <label>
                Baseline
                <select
                  aria-label="Baseline"
                  value={baseline}
                  onChange={(e) => setBaseline(e.target.value)}
                >
                  <option value="">Choose baseline</option>
                  {runs.map((r) => (
                    <option value={r.id} key={r.id}>
                      {r.id.slice(0, 8)} · {r.status}
                    </option>
                  ))}
                </select>
              </label>
              <label>
                Candidate
                <select
                  aria-label="Candidate"
                  value={candidate}
                  onChange={(e) => setCandidate(e.target.value)}
                >
                  <option value="">Choose candidate</option>
                  {runs.map((r) => (
                    <option value={r.id} key={r.id}>
                      {r.id.slice(0, 8)} · {r.status}
                    </option>
                  ))}
                </select>
              </label>
            </div>
            <button
              disabled={busy || !baseline || !candidate}
              onClick={() =>
                action(async () =>
                  setComparison(
                    await api<Comparison>("/comparisons", {
                      baseline_run_id: baseline,
                      candidate_run_id: candidate,
                    }),
                  ),
                )
              }
            >
              Compare runs
            </button>
            {comparison && (
              <div className="comparison">
                <h3 className={"badge " + comparison.outcome.toLowerCase()}>
                  {comparison.outcome}
                </h3>
                <p>{comparison.paired_cases} paired cases</p>
                {comparison.reasons.map((reason) => (
                  <p key={reason}>{reason}</p>
                ))}
                <table>
                  <tbody>
                    {Object.entries(comparison.metrics).map(([key, value]) => (
                      <tr key={key}>
                        <td>{key.replaceAll("_", " ")}</td>
                        <td>{number(value)}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
            <p className="muted">
              Incomplete coverage or incompatible judges are inconclusive.
              Thresholds are demonstration policies, not statistical
              significance.
            </p>
          </section>
        )}
        {view === "Judge study" && (
          <>
            <section>
              <h2>Human vs. AI agreement</h2>
              <p className="intro">{studySummary(study)}</p>
              <p className="muted">
                Judge prompt {study?.judge_prompt_version ?? "v1"}
                {study?.scope ? " · " + study.scope : ""}
              </p>
              <div className="stats">
                <article>
                  <span>Human labels</span>
                  <strong>{study?.human_labeled ?? 0}</strong>
                </article>
                <article>
                  <span>Paired examples</span>
                  <strong>{study?.paired_count ?? 0}</strong>
                </article>
                <article>
                  <span>Agreement</span>
                  <strong>
                    {study?.agreement == null
                      ? "—"
                      : number(study.agreement * 100, "%")}
                  </strong>
                </article>
              </div>
              <h3>Confusion matrix · positive = quality pass</h3>
              <table>
                <tbody>
                  {Object.entries(study?.confusion_matrix ?? {}).map(
                    ([name, count]) => (
                      <tr key={name}>
                        <td>{name.toUpperCase()}</td>
                        <td>{study?.paired_count ? count : "—"}</td>
                      </tr>
                    ),
                  )}
                </tbody>
              </table>
              <h3>Disagreements</h3>
              {study?.disagreements?.length ? (
                study.disagreements.map((d) => (
                  <p key={d.example_id}>
                    {d.example_id} · {d.category}
                  </p>
                ))
              ) : (
                <p className="muted">No measured disagreements to display.</p>
              )}
            </section>
          </>
        )}
        <footer>
          AgentEval · evidence before claims · local/controlled demonstration
        </footer>
      </main>
    </div>
  );
}
createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>,
);
