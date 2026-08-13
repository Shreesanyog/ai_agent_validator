import { useState } from "react";
import { api } from "../api.js";

const DEFAULT_TOOLS = `[
  {
    "name": "get_order_status",
    "description": "Look up an order's shipping status",
    "parameters": {
      "type": "object",
      "properties": { "order_id": { "type": "string" } },
      "required": ["order_id"]
    }
  }
]`;

export default function AgentOnboardingForm({ onAgentCreated }) {
  const [form, setForm] = useState({
    name: "",
    endpoint_url: "",
    description: "",
    system_prompt: "",
    tools: DEFAULT_TOOLS,
    disallowed_tools: "",
  });
  const [result, setResult] = useState(null);
  const [error, setError] = useState("");

  function update(field, value) {
    setForm((f) => ({ ...f, [field]: value }));
  }

  async function submit(e) {
    e.preventDefault();
    setError("");
    let tools;
    try {
      tools = JSON.parse(form.tools || "[]");
    } catch (err) {
      setError(`Invalid tools JSON: ${err.message}`);
      return;
    }
    const payload = {
      name: form.name,
      endpoint_url: form.endpoint_url,
      description: form.description,
      system_prompt: form.system_prompt,
      tools,
      disallowed_tools: form.disallowed_tools.split(",").map((s) => s.trim()).filter(Boolean),
    };
    try {
      const agent = await api("/api/agents", { method: "POST", body: JSON.stringify(payload) });
      setResult(agent);
      onAgentCreated?.(agent);
    } catch (err) {
      setError(err.message);
    }
  }

  return (
    <div className="panel">
      <h2>Onboard an Agent</h2>
      <form onSubmit={submit}>
        <label>Name
          <input value={form.name} onChange={(e) => update("name", e.target.value)} required placeholder="Support Bot" />
        </label>
        <label>Endpoint URL
          <input value={form.endpoint_url} onChange={(e) => update("endpoint_url", e.target.value)} required placeholder="http://localhost:9000/invoke" />
        </label>
        <label>Description
          <input value={form.description} onChange={(e) => update("description", e.target.value)} placeholder="Customer support agent" />
        </label>
        <label>System prompt
          <textarea rows={2} value={form.system_prompt} onChange={(e) => update("system_prompt", e.target.value)} placeholder="You are a helpful support agent..." />
        </label>
        <label>Tools (JSON array)
          <textarea rows={7} value={form.tools} onChange={(e) => update("tools", e.target.value)} />
        </label>
        <label>Disallowed tools (comma-separated, optional)
          <input value={form.disallowed_tools} onChange={(e) => update("disallowed_tools", e.target.value)} placeholder="delete_account, wire_transfer" />
        </label>
        <button className="primary" type="submit">Register Agent</button>
      </form>
      {error && <p className="error">{error}</p>}
      {result && (
        <div style={{ marginTop: "0.75rem" }}>
          <p>Registered: <b>{result.id}</b></p>
          <pre>{JSON.stringify(result, null, 2)}</pre>
        </div>
      )}
    </div>
  );
}
