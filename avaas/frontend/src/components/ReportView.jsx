import { getApiKey } from "../api.js";

// Analytics / failure-analysis view for a single run: release gate,
// requirement coverage, per-tier score breakdown, and regression summary
// when the run was compared against a baseline.
export default function ReportView({ report }) {
  if (!report) {
    return (
      <div className="panel">
        <h2>Report</h2>
        <p className="hint">Select a run on the left to see its analytics and failure analysis.</p>
      </div>
    );
  }

  const coverageEntries = Object.entries(report.requirement_coverage || {});
  const reqById = Object.fromEntries((report.requirement_analysis?.requirements || []).map((r) => [r.requirement_id, r]));

  const htmlReportUrl = `/api/runs/${report.run_id}/html`;

  return (
    <div className="panel">
      <h2>Report — {report.agent_name}</h2>
      <p>
        <span className={`badge ${report.release_gate}`}>{report.release_gate}</span>{" "}
        <a href={htmlReportUrl + (getApiKey() ? "" : "")} target="_blank" rel="noreferrer">Open full HTML report ↗</a>
      </p>

      <div className="stat-grid">
        <div className="stat"><div className="value">{(report.pass_rate * 100).toFixed(1)}%</div><div className="label">Pass rate</div></div>
        <div className="stat"><div className="value">{report.avg_score}</div><div className="label">Avg composite score</div></div>
        <div className="stat"><div className="value">{report.test_cases_count}</div><div className="label">Test cases</div></div>
        <div className="stat"><div className="value">{coverageEntries.length}</div><div className="label">Requirements tracked</div></div>
      </div>

      {report.regression && (
        <>
          <h3>Regression vs baseline {report.regression.baseline_run_id}</h3>
          <p className={report.regression.regressed ? "error" : ""}>
            {report.regression.regressed ? "Regression detected" : "No regression"} — pass rate{" "}
            {(report.regression.baseline_pass_rate * 100).toFixed(1)}% → {(report.regression.candidate_pass_rate * 100).toFixed(1)}%{" "}
            ({report.regression.pass_rate_delta >= 0 ? "+" : ""}{(report.regression.pass_rate_delta * 100).toFixed(1)}pp)
          </p>
          {report.regression.regressed_test_case_types.length > 0 && (
            <div className="pill-row">
              {report.regression.regressed_test_case_types.map((t) => <span className="pill" key={t}>{t}</span>)}
            </div>
          )}
        </>
      )}

      <h3>Requirement coverage</h3>
      <table>
        <thead><tr><th>Requirement</th><th>Source</th><th>Status</th></tr></thead>
        <tbody>
          {coverageEntries.map(([rid, status]) => (
            <tr key={rid}>
              <td>{reqById[rid]?.requirement || rid}</td>
              <td>{reqById[rid]?.source || "-"}</td>
              <td><span className={`badge ${status === "PASS" ? "PASS" : status === "FAIL" ? "FAIL" : ""}`} style={status === "UNTESTED" ? { background: "#9c7c00" } : {}}>{status}</span></td>
            </tr>
          ))}
        </tbody>
      </table>

      <h3>Test results (rule / safety / business / composite)</h3>
      <table>
        <thead><tr><th>Type</th><th>Rule</th><th>Safety</th><th>Business</th><th>Composite</th><th>Status</th></tr></thead>
        <tbody>
          {report.results.map((r) => (
            <tr key={r.test_case_id}>
              <td>{r.test_case_type}</td>
              <td>{r.rule_score}</td>
              <td>{r.safety_score ?? "-"}</td>
              <td>{r.business_score ?? "-"}</td>
              <td>{r.composite_score}</td>
              <td><span className={`badge ${r.passed ? "PASS" : "FAIL"}`}>{r.passed ? "PASS" : "FAIL"}</span></td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
