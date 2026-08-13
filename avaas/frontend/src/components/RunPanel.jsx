import { useState } from "react";
import { api } from "../api.js";

export default function RunPanel({ agentId, useCase, requirements, onRunComplete }) {
  const [isBaseline, setIsBaseline] = useState(false);
  const [maxTestCases, setMaxTestCases] = useState("");
  const [running, setRunning] = useState(false);
  const [error, setError] = useState("");
  const [result, setResult] = useState(null);

  async function submit(e) {
    e.preventDefault();
    setError("");
    setResult(null);
    setRunning(true);
    try {
      const payload = {
        agent_id: agentId,
        use_case_definition: useCase,
        business_requirements: requirements.split("\n").map((s) => s.trim()).filter(Boolean),
        is_baseline: isBaseline,
      };
      if (maxTestCases) payload.max_test_cases = Number(maxTestCases);
      const report = await api("/api/runs", { method: "POST", body: JSON.stringify(payload) });
      setResult(report);
      onRunComplete?.(report);
    } catch (err) {
      setError(err.message);
    } finally {
      setRunning(false);
    }
  }

  return (
    <div className="panel">
      <h2>Run Validation</h2>
      {!agentId && <p className="hint">Register or select an agent first.</p>}
      <form onSubmit={submit}>
        <label>Agent ID
          <input value={agentId || ""} readOnly placeholder="agent_..." />
        </label>
        <label style={{ display: "flex", flexDirection: "row", alignItems: "center", gap: "0.5rem" }}>
          <input type="checkbox" style={{ width: "auto" }} checked={isBaseline} onChange={(e) => setIsBaseline(e.target.checked)} />
          Mark as baseline
        </label>
        <label>Max test cases (optional, for a quick demo run)
          <input type="number" min="1" value={maxTestCases} onChange={(e) => setMaxTestCases(e.target.value)} placeholder="leave empty for full suite" />
        </label>
        <button className="primary" type="submit" disabled={!agentId || running}>
          {running ? "Running..." : "Run Validation"}
        </button>
      </form>
      {error && <p className="error">{error}</p>}
      {result && (
        <div style={{ marginTop: "0.75rem" }}>
          <p>
            Run <b>{result.run_id}</b> — <span className={`badge ${result.release_gate}`}>{result.release_gate}</span>
          </p>
          <p className="hint">Pass rate {(result.pass_rate * 100).toFixed(1)}% · Avg score {result.avg_score}</p>
        </div>
      )}
    </div>
  );
}
