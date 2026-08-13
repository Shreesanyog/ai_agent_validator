import { useEffect, useState } from "react";
import { api } from "../api.js";

export default function RunsList({ agentId, refreshKey, onSelectRun, selectedRunId }) {
  const [runs, setRuns] = useState([]);
  const [error, setError] = useState("");

  useEffect(() => {
    load();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [agentId, refreshKey]);

  async function load() {
    setError("");
    try {
      const qs = agentId ? `?agent_id=${agentId}` : "";
      const data = await api(`/api/runs${qs}`);
      setRuns(data);
    } catch (err) {
      setError(err.message);
    }
  }

  return (
    <div className="panel">
      <h2>Runs {agentId ? "" : "(all agents)"}</h2>
      <button className="secondary" type="button" onClick={load}>Refresh</button>
      {error && <p className="error">{error}</p>}
      {runs.length === 0 && <p className="hint">No runs yet.</p>}
      {runs.map((r) => (
        <div
          key={r.run_id}
          className={`run-card ${selectedRunId === r.run_id ? "selected" : ""}`}
          onClick={() => onSelectRun(r)}
        >
          <p style={{ margin: 0 }}>
            <b>{r.agent_name}</b> {r.is_baseline ? "(baseline)" : ""} — <span className={`badge ${r.release_gate}`}>{r.release_gate}</span>
          </p>
          <p className="hint" style={{ margin: "0.2rem 0 0 0" }}>
            {r.run_id} · pass {(r.pass_rate * 100).toFixed(1)}% · score {r.avg_score}
          </p>
        </div>
      ))}
    </div>
  );
}
