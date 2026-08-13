import { useState } from "react";
import { api, getApiKey, setApiKey } from "../api.js";

// Multi-tenant onboarding: create a tenant (returns an API key) or paste an
// existing one. The key is stored in localStorage and attached as
// X-API-Key on every subsequent request (see api.js).
export default function TenantPanel({ onTenantChange }) {
  const [name, setName] = useState("");
  const [keyInput, setKeyInput] = useState(getApiKey());
  const [result, setResult] = useState(null);
  const [error, setError] = useState("");

  async function createTenant(e) {
    e.preventDefault();
    setError("");
    try {
      const tenant = await api("/api/tenants", { method: "POST", body: JSON.stringify({ name }) });
      setApiKey(tenant.api_key);
      setKeyInput(tenant.api_key);
      setResult(tenant);
      onTenantChange?.(tenant.api_key);
    } catch (err) {
      setError(err.message);
    }
  }

  function useExistingKey(e) {
    e.preventDefault();
    setApiKey(keyInput);
    onTenantChange?.(keyInput);
  }

  return (
    <div className="panel">
      <h2>Tenant</h2>
      <p className="hint">Every agent and run is scoped to a tenant. Create one, or paste an existing API key.</p>
      <form onSubmit={createTenant}>
        <label>New tenant name
          <input value={name} onChange={(e) => setName(e.target.value)} placeholder="Acme QA Team" />
        </label>
        <button className="primary" type="submit" disabled={!name}>Create tenant</button>
      </form>
      {result && (
        <div style={{ marginTop: "0.75rem" }}>
          <p className="hint">Save this API key — it won't be shown again by the API (though it's stored in your browser now).</p>
          <pre>{JSON.stringify(result, null, 2)}</pre>
        </div>
      )}
      <form onSubmit={useExistingKey} style={{ marginTop: "1rem", borderTop: "1px solid #eee", paddingTop: "0.75rem" }}>
        <label>Use existing API key
          <input value={keyInput} onChange={(e) => setKeyInput(e.target.value)} placeholder="avaas_..." />
        </label>
        <button className="secondary" type="submit">Use this key</button>
      </form>
      {error && <p className="error">{error}</p>}
    </div>
  );
}
