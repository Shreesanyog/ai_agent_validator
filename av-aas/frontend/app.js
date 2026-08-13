const API_BASE = "";

async function api(path, options = {}) {
  const res = await fetch(`${API_BASE}${path}`, {
    headers: { "Content-Type": "application/json" },
    ...options,
  });
  const contentType = res.headers.get("content-type") || "";
  const body = contentType.includes("application/json") ? await res.json() : await res.text();
  if (!res.ok) {
    throw new Error(typeof body === "string" ? body : JSON.stringify(body));
  }
  return body;
}

document.getElementById("agent-form").addEventListener("submit", async (e) => {
  e.preventDefault();
  const form = new FormData(e.target);
  let tools = [];
  try {
    tools = JSON.parse(form.get("tools") || "[]");
  } catch (err) {
    document.getElementById("agent-result").innerHTML = `<p style="color:red">Invalid tools JSON: ${err}</p>`;
    return;
  }
  const payload = {
    name: form.get("name"),
    endpoint_url: form.get("endpoint_url"),
    description: form.get("description") || "",
    system_prompt: form.get("system_prompt") || "",
    tools,
  };
  try {
    const agent = await api("/api/agents", { method: "POST", body: JSON.stringify(payload) });
    document.getElementById("agent-result").innerHTML = `<p>Registered: <b>${agent.id}</b></p><pre>${JSON.stringify(agent, null, 2)}</pre>`;
    document.getElementById("run-agent-id").value = agent.id;
  } catch (err) {
    document.getElementById("agent-result").innerHTML = `<p style="color:red">${err.message}</p>`;
  }
});

document.getElementById("run-form").addEventListener("submit", async (e) => {
  e.preventDefault();
  const form = new FormData(e.target);
  const explicitText = (form.get("explicit_requirements") || "").trim();
  const payload = {
    agent_id: form.get("agent_id"),
    is_baseline: form.get("is_baseline") === "on",
    explicit_requirements: explicitText ? explicitText.split("\n").filter(Boolean) : [],
  };
  const resultDiv = document.getElementById("run-result");
  resultDiv.innerHTML = "<p>Running validation... this executes every generated test case against the agent endpoint.</p>";
  try {
    const report = await api("/api/runs", { method: "POST", body: JSON.stringify(payload) });
    resultDiv.innerHTML = renderReportSummary(report);
    loadRuns();
  } catch (err) {
    resultDiv.innerHTML = `<p style="color:red">${err.message}</p>`;
  }
});

function renderReportSummary(report) {
  const gateClass = `gate-${report.release_gate}`;
  let regressionHtml = "";
  if (report.regression) {
    regressionHtml = `<p>Regression: <b>${report.regression.regressed ? "YES" : "no"}</b> (pass rate ${(report.regression.baseline_pass_rate*100).toFixed(1)}% &rarr; ${(report.regression.candidate_pass_rate*100).toFixed(1)}%)</p>`;
  }
  return `
    <div class="run-card">
      <p><b>${report.agent_name}</b> — run ${report.run_id} ${report.is_baseline ? "(baseline)" : ""}</p>
      <p>Pass rate: ${(report.pass_rate * 100).toFixed(1)}% | Avg score: ${report.avg_score} | Gate: <span class="${gateClass}">${report.release_gate}</span></p>
      ${regressionHtml}
      <p><a href="/api/runs/${report.run_id}/html" target="_blank">View full HTML report &rarr;</a></p>
    </div>`;
}

async function loadRuns() {
  const listDiv = document.getElementById("runs-list");
  try {
    const runs = await api("/api/runs");
    listDiv.innerHTML = runs.length ? runs.map(renderReportSummary).join("") : "<p>No runs yet.</p>";
  } catch (err) {
    listDiv.innerHTML = `<p style="color:red">${err.message}</p>`;
  }
}

document.getElementById("refresh-runs").addEventListener("click", loadRuns);
loadRuns();
