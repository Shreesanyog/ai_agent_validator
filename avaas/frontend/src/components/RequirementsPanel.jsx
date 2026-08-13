import { useState } from "react";
import { api } from "../api.js";

// Business Requirement input panel: lets a QA engineer input a use case
// definition and explicit business requirements/acceptance criteria, and
// preview the structured Requirement & Use Case Analysis before committing
// to a full validation run (POST /api/requirements/analyze -> same engine
// POST /api/runs uses internally).
export default function RequirementsPanel({ agentId, useCase, setUseCase, requirements, setRequirements }) {
  const [preview, setPreview] = useState(null);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  async function previewAnalysis() {
    setError("");
    setLoading(true);
    try {
      const analysis = await api(`/api/requirements/analyze${agentId ? `?agent_id=${agentId}` : ""}`, {
        method: "POST",
        body: JSON.stringify({
          use_case_definition: useCase,
          business_requirements: requirements.split("\n").map((s) => s.trim()).filter(Boolean),
        }),
      });
      setPreview(analysis);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="panel">
      <h2>Business Requirements</h2>
      <p className="hint">
        Explicit requirements always take priority over anything inferred from the agent's tools/prompt — see
        docs/requirement_analysis.md.
      </p>
      <label>Use case definition
        <textarea rows={2} value={useCase} onChange={(e) => setUseCase(e.target.value)}
          placeholder="Customer wants to check an order's status and, if eligible, request a refund." />
      </label>
      <label>Business requirements / acceptance criteria (one per line)
        <textarea rows={4} value={requirements} onChange={(e) => setRequirements(e.target.value)}
          placeholder={"Refunds over $500 require the agent to ask for a manager approval code.\nThe agent must always confirm the order id before refunding."} />
      </label>
      <button className="secondary" type="button" onClick={previewAnalysis} disabled={loading}>
        {loading ? "Analyzing..." : "Preview requirement analysis"}
      </button>
      {error && <p className="error">{error}</p>}
      {preview && (
        <div style={{ marginTop: "0.75rem" }}>
          <div className="stat-grid">
            <div className="stat"><div className="value">{preview.analysis_summary.explicit_requirement_count}</div><div className="label">Explicit</div></div>
            <div className="stat"><div className="value">{preview.analysis_summary.derived_requirement_count}</div><div className="label">Derived</div></div>
            <div className="stat"><div className="value">{preview.analysis_summary.inferred_requirement_count}</div><div className="label">Inferred</div></div>
            <div className="stat"><div className="value">{preview.analysis_summary.requirement_gap_count}</div><div className="label">Gaps</div></div>
          </div>
          {preview.requirement_gaps.length > 0 && (
            <>
              <h3>Requirement gaps</h3>
              <ul>
                {preview.requirement_gaps.map((g) => (
                  <li key={g.gap_id}><b>[{g.impact}]</b> {g.description} — <i>{g.question_for_qa}</i></li>
                ))}
              </ul>
            </>
          )}
          <h3>Test scenarios ({preview.test_scenarios.length})</h3>
          <div className="pill-row">
            {preview.test_scenarios.map((s) => <span className="pill" key={s.scenario_id}>{s.type}</span>)}
          </div>
        </div>
      )}
    </div>
  );
}
