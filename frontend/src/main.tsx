import React, { useEffect, useState } from 'react';
import { createRoot } from 'react-dom/client';
import { Bot, Globe2, Play, ShieldCheck, Plus, Search, Activity, ChevronDown, ChevronUp, TerminalSquare } from 'lucide-react';
import Swal from 'sweetalert2';

// @ts-ignore
import './index.css';

// @ts-ignore
const A = import.meta.env.VITE_API_URL || 'http://localhost:8000/api/v1';

async function api(p: string, o: RequestInit = {}) {
  const r = await fetch(A + p, {
    ...o,
    headers: {
      'Content-Type': 'application/json',
      Authorization: `Bearer ${localStorage.access}`,
      ...(o.headers || {})
    }
  });
  if (!r.ok) throw Error(await r.text());
  return r.json();
}

function Auth({ done }: { done: () => void }) {
  const [f, setF] = useState({ organization: 'Acme QA', slug: 'acme-qa', email: 'owner@example.com', password: 'ChangeMe123!' });
  const [login, setLogin] = useState(false);

  async function go() {
    try {
      const body = login ? { tenant_slug: f.slug, email: f.email, password: f.password } : f;
      const x = await api('/auth/' + (login ? 'login' : 'register'), { method: 'POST', body: JSON.stringify(body) });
      localStorage.access = x.access_token;
      localStorage.refresh = x.refresh_token;
      await Swal.fire({ icon: 'success', title: login ? 'Welcome back!' : 'Registration Successful', background: '#0f172a', color: '#f8fafc', timer: 1500, showConfirmButton: false });
      done();
    } catch (x) {
      let errorMsg = String(x);
      if (errorMsg.includes('Failed to fetch')) errorMsg = "Cannot connect to the backend server. Please ensure the FastAPI server is running on port 8000.";
      else { try { const parsed = JSON.parse(errorMsg.replace('Error: ', '')); errorMsg = parsed.detail || errorMsg; } catch (e) {} }
      Swal.fire({ icon: 'error', title: login ? 'Login Failed' : 'Registration Failed', text: errorMsg, confirmButtonColor: '#7c3aed', background: '#0f172a', color: '#f8fafc' });
    }
  }

  return (
    <div className="min-h-screen grid place-items-center bg-[radial-gradient(circle_at_top,#332766,#020617_55%)]">
      <div className="card w-[420px]">
        <div className="flex items-center gap-3">
          <ShieldCheck className="text-violet-400" />
          <h1 className="text-2xl font-bold">AVaaS Enterprise</h1>
        </div>
        <p className="my-4 text-slate-400">Tenant-isolated governance for browser and API agents.</p>
        {!login && <input className="mt-3" value={f.organization} onChange={(e) => setF({ ...f, organization: e.target.value })} placeholder="Organization" />}
        <input className="mt-3" value={f.slug} onChange={(e) => setF({ ...f, slug: e.target.value })} placeholder="Tenant slug" />
        <input className="mt-3" value={f.email} onChange={(e) => setF({ ...f, email: e.target.value })} placeholder="Email address" />
        <input className="mt-3" type="password" value={f.password} onChange={(e) => setF({ ...f, password: e.target.value })} placeholder="Password" />
        <button className="mt-4 w-full bg-violet-600 hover:bg-violet-500" onClick={go}>{login ? 'Sign in' : 'Create organization'}</button>
        <button className="mt-3 w-full text-slate-400 hover:text-slate-200 transition" onClick={() => setLogin(!login)}>{login ? 'Need an organization? Register' : 'Already registered? Sign in'}</button>
      </div>
    </div>
  );
}

function App() {
  const [ok, setOk] = useState(!!localStorage.access);
  const [projects, setProjects] = useState<any[]>([]);
  const [targets, setTargets] = useState<any[]>([]);
  const [runs, setRuns] = useState<any[]>([]);
  const [runDetails, setRunDetails] = useState<Record<string, any[]>>({});
  
  const [pid, setPid] = useState('');
  const [name, setName] = useState('');
  const [url, setUrl] = useState('');
  const [mode, setMode] = useState('browser');
  const [customConfig, setCustomConfig] = useState('');
  const [msg, setMsg] = useState('');

  async function load() {
    try {
      const p = await api('/projects');
      setProjects(p);
      setRuns(await api('/runs'));
      if (p[0] && !pid) {
        setPid(p[0].id);
        setTargets(await api(`/projects/${p[0].id}/targets`));
      } else if (pid) {
        setTargets(await api(`/projects/${pid}/targets`));
      }
    } catch (e) { console.error(e); }
  }

  useEffect(() => {
    if (!ok) return;
    load();
    const interval = setInterval(load, 3000);
    return () => clearInterval(interval);
  }, [ok, pid]);

  if (!ok) return <Auth done={() => setOk(true)} />;

  async function createProject() {
    await api('/projects', { method: 'POST', body: JSON.stringify({ name: name || 'Agent Validation', description: '' }) });
    setName('');
    load();
  }

  async function add() {
    let parsedConfig = {};
    if (customConfig.trim()) {
      try { parsedConfig = JSON.parse(customConfig); } 
      catch (e) { Swal.fire({ icon: 'error', title: 'Invalid JSON', text: 'Please ensure your Advanced Config is valid JSON format.', background: '#0f172a', color: '#f8fafc' }); return; }
    }
    const t = await api(`/projects/${pid}/targets`, { method: 'POST', body: JSON.stringify({ name: name || new URL(url).hostname, base_url: url, mode, config: parsedConfig }) });
    setMsg('Target saved. Running discovery...');
    const d = await api(`/targets/${t.id}/discover`, { method: 'POST' });
    setMsg(d.ready ? 'Interaction discovered successfully.' : 'Discovery finished. Utilizing your custom selectors.');
    load();
  }

  async function toggleRunDetails(runId: string) {
    if (runDetails[runId]) {
      const newDetails = { ...runDetails };
      delete newDetails[runId];
      setRunDetails(newDetails);
    } else {
      try {
        const data = await api(`/runs/${runId}`);
        setRunDetails({ ...runDetails, [runId]: data.results });
      } catch (e) { console.error("Failed to fetch run details", e); }
    }
  }

  return (
    <div className="min-h-screen pb-20">
      <header className="border-b border-slate-800 bg-slate-950/80 px-8 py-4 backdrop-blur sticky top-0 z-50">
        <div className="mx-auto flex max-w-7xl items-center justify-between">
          <div className="flex items-center gap-3">
            <Bot className="text-violet-400" />
            <b className="text-xl">AVaaS</b>
            <span className="text-slate-500">Enterprise Control Plane</span>
          </div>
          <button className="border border-slate-700 hover:bg-slate-800" onClick={() => { localStorage.clear(); setOk(false); }}>Sign out</button>
        </div>
      </header>
      
      <main className="mx-auto max-w-7xl p-8">
        <section className="grid grid-cols-4 gap-4">
          {[
            ['Projects', projects.length],
            ['Targets', targets.length],
            ['Total Runs', runs.length],
            ['Pass gates', runs.filter(x => x.release_gate === 'PASS').length]
          ].map((x, i) => (
            <div key={i} className="card bg-slate-900/40 border-slate-800/60">
              <p className="text-slate-400 font-medium tracking-wide uppercase text-xs">{x[0]}</p>
              <p className="mt-2 text-4xl font-black text-slate-100">{x[1]}</p>
            </div>
          ))}
        </section>

        <section className="mt-6 grid grid-cols-3 gap-6">
          <div className="card col-span-2">
            <h2 className="text-lg font-semibold mb-2">Universal agent onboarding</h2>
            <p className="mb-6 text-sm text-slate-400">Give AVaaS a public URL. If auto-discovery fails on complex UIs, provide exact CSS selectors in the Advanced Config.</p>
            <div className="grid grid-cols-2 gap-4">
              <select value={pid} onChange={(e) => setPid(e.target.value)}>
                <option value="">Select project</option>
                {projects.map((p: any) => <option key={p.id} value={p.id}>{p.name}</option>)}
              </select>
              <select value={mode} onChange={(e) => setMode(e.target.value)}>
                <option value="browser">Browser website</option>
                <option value="openapi">OpenAPI</option>
              </select>
              <input value={name} onChange={(e) => setName(e.target.value)} placeholder="Target name (optional)" />
              <input value={url} onChange={(e) => setUrl(e.target.value)} placeholder="https://agent.example.com" />
            </div>
            
            <div className="mt-4">
              <label className="block text-xs font-bold text-slate-500 uppercase tracking-wider mb-2">Advanced Config (JSON) - Optional</label>
              <textarea 
                className="font-mono text-xs h-20"
                value={customConfig}
                onChange={(e) => setCustomConfig(e.target.value)}
                placeholder='{"input_selector": "#chat-input", "submit_selector": "#send-btn", "response_selector": ".message-bubble"}'
              />
            </div>

            <button className="mt-6 flex items-center gap-2 bg-violet-600 px-6" disabled={!pid || !url} onClick={add}>
              <Search size={17} />Discover agent
            </button>
            <p className="mt-3 text-sm text-violet-300 font-medium">{msg}</p>
          </div>
          
          <div className="card h-fit">
            <h2 className="font-semibold mb-4">New project</h2>
            <input value={name} onChange={(e) => setName(e.target.value)} placeholder="Project name" />
            <button className="mt-4 flex gap-2 bg-slate-800 hover:bg-slate-700 w-full justify-center" onClick={createProject}>
              <Plus size={17} />Create Project
            </button>
          </div>
        </section>

        <section className="mt-6 card">
          <h2 className="text-lg font-semibold mb-4">Discovered Targets</h2>
          <div className="space-y-3">
            {targets.length === 0 ? <p className="text-slate-500 text-sm">No targets added yet.</p> : targets.map((t: any) => (
              <div key={t.id} className="flex items-center justify-between rounded-xl border border-slate-800 bg-slate-900/50 p-4">
                <div>
                  <div className="flex items-center gap-2 mb-1">
                    <Globe2 size={16} className="text-cyan-400" />
                    <b className="text-slate-200">{t.name}</b>
                    <span className="rounded-md bg-slate-800 px-2 py-0.5 text-[10px] uppercase font-bold tracking-wider text-slate-400">{t.mode}</span>
                  </div>
                  <p className="text-xs text-slate-500">{t.base_url}</p>
                </div>
                <button className="flex items-center gap-2 bg-emerald-600 hover:bg-emerald-500 text-sm" onClick={async () => {
                  await api(`/targets/${t.id}/runs`, { method: 'POST', body: JSON.stringify({ max_cases: 3, optional_context: '' }) });
                  load(); 
                }}>
                  <Play size={16} /> Run QA Pipeline
                </button>
              </div>
            ))}
          </div>
        </section>

        <section className="mt-6 card">
          <h2 className="text-lg font-semibold mb-4 flex items-center gap-2">
            <Activity className="text-violet-400" size={20} /> Recent Test Analysis & Results
          </h2>
          <div className="space-y-4">
            {runs.length === 0 ? <p className="text-slate-500 text-sm">Waiting for first validation run...</p> : runs.map((r: any) => (
              <div key={r.id} className="rounded-xl border border-slate-800 bg-slate-900/50 p-5">
                <div className="flex justify-between items-center mb-4 pb-4 border-b border-slate-800/60">
                  <div>
                    <span className="text-xs text-slate-500 block mb-1">TEST RUN ID</span>
                    <span className="font-mono text-sm text-slate-300">#{r.id.split('-')[0]}</span>
                  </div>
                  <div>
                    {r.status === 'running' && <span className="px-3 py-1 rounded-full text-xs font-bold bg-amber-500/20 text-amber-400 animate-pulse">⚙️ RUNNING IN BACKGROUND...</span>}
                    {r.status === 'completed' && <span className="px-3 py-1 rounded-full text-xs font-bold bg-blue-500/20 text-blue-400">✅ COMPLETED</span>}
                    {r.status === 'failed' && <span className="px-3 py-1 rounded-full text-xs font-bold bg-red-500/20 text-red-400">❌ CRASHED</span>}
                  </div>
                </div>

                <div className="grid grid-cols-5 gap-6">
                  <div>
                    <p className="text-xs font-bold text-slate-500 uppercase tracking-wider mb-1">Release Gate</p>
                    <p className={`text-xl font-black ${r.release_gate === 'PASS' ? 'text-emerald-400' : 'text-rose-500'}`}>
                      {r.release_gate || (r.status === 'running' ? 'PENDING' : 'FAIL')}
                    </p>
                  </div>
                  <div>
                    <p className="text-xs font-bold text-slate-500 uppercase tracking-wider mb-1">Composite Score</p>
                    <p className="text-lg font-bold text-slate-200">{r.score ? r.score.toFixed(1) : 0} <span className="text-sm text-slate-600">/ 100</span></p>
                  </div>
                  <div>
                    <p className="text-xs font-bold text-slate-500 uppercase tracking-wider mb-1">Pass Rate</p>
                    <p className="text-lg font-bold text-slate-200">{r.pass_rate ? (r.pass_rate * 100).toFixed(0) : 0}%</p>
                  </div>
                  <div className="col-span-2">
                    <p className="text-xs font-bold text-slate-500 uppercase tracking-wider mb-1">QA Telemetry</p>
                    <div className="text-xs text-slate-300 font-mono mt-1 space-y-1">
                      <p>Engine: <span className="text-violet-300 uppercase font-bold">{r.summary?.llm_provider || 'Evaluating...'}</span></p>
                      <p>Tokens Used: {r.summary?.tokens ? (r.summary.tokens.prompt + r.summary.tokens.completion).toLocaleString() : 0}</p>
                      <p>Est. Cost: <span className="text-emerald-400">${r.summary?.estimated_cost ? r.summary.estimated_cost.toFixed(5) : '0.00000'}</span></p>
                    </div>
                  </div>
                </div>

                {r.status === 'completed' && (
                  <button onClick={() => toggleRunDetails(r.id)} className="mt-5 w-full flex justify-center items-center gap-2 py-2 bg-slate-800 hover:bg-slate-700 text-slate-300 text-sm font-medium rounded-lg transition">
                    {runDetails[r.id] ? <><ChevronUp size={16}/> Hide Detailed Report</> : <><ChevronDown size={16}/> View Detailed Report</>}
                  </button>
                )}

                {runDetails[r.id] && (
                  <div className="mt-4 pt-4 border-t border-slate-700 space-y-4">
                    <h3 className="text-sm font-bold text-slate-400 mb-3 flex items-center gap-2"><TerminalSquare size={16}/> EXECUTED TEST CASES & EVIDENCE</h3>
                    {runDetails[r.id].map((res: any) => (
                      <div key={res.id} className="bg-slate-950 p-4 rounded-lg border border-slate-800">
                        <div className="flex justify-between items-center mb-3">
                          <div>
                            <span className="px-2 py-1 bg-slate-800 text-slate-300 text-[10px] font-bold uppercase rounded">{res.case_type} Case</span>
                            {res.evidence?.hallucination_detected && (
                              <span className="ml-2 px-2 py-1 bg-rose-500/20 text-rose-400 text-[10px] font-bold uppercase rounded border border-rose-500/30">
                                ⚠️ Hallucination Detected
                              </span>
                            )}
                          </div>
                          <span className={`px-2 py-1 text-[10px] font-bold uppercase rounded ${res.passed ? 'bg-emerald-500/20 text-emerald-400' : 'bg-rose-500/20 text-rose-400'}`}>
                            {res.passed ? 'PASSED' : 'FAILED'}
                          </span>
                        </div>
                        <div className="mb-3"><span className="text-[10px] font-bold text-slate-500 uppercase tracking-wider block mb-1">Generated Prompt</span><p className="text-sm text-slate-300 font-mono bg-slate-900/50 p-2 rounded">{res.prompt}</p></div>
                        <div className="mb-3"><span className="text-[10px] font-bold text-slate-500 uppercase tracking-wider block mb-1">Agent Response / Error Output</span><p className={`text-sm font-mono bg-slate-900/50 p-2 rounded ${!res.response || res.response.includes('Error') || res.response.includes('crashed') ? 'text-rose-400' : 'text-slate-300'}`}>{res.response || "No response received or adapter crashed."}</p></div>
                        <div className="grid grid-cols-2 gap-4 border-t border-slate-800 pt-3 mt-3">
                          <div><span className="text-[10px] font-bold text-slate-500 uppercase tracking-wider block mb-1">LLM Judge Rationale</span><ul className="text-xs text-slate-400 list-disc pl-4">{res.rationale && res.rationale.length > 0 ? res.rationale.map((r: string, idx: number) => <li key={idx}>{r}</li>) : <li>No rationale provided.</li>}</ul></div>
                          <div><span className="text-[10px] font-bold text-slate-500 uppercase tracking-wider block mb-1">Trace Evidence</span><div className="text-xs text-slate-400 font-mono">Latency: {res.evidence?.latency_ms ? res.evidence.latency_ms.toFixed(0) : 0}ms <br/>Adapter: {res.evidence?.adapter || 'N/A'} <br/>Tokens Used: {res.evidence?.tokens ? (res.evidence.tokens.prompt + res.evidence.tokens.completion).toLocaleString() : 0}</div></div>
                        </div>
                      </div>
                    ))}
                  </div>
                )}
              </div>
            ))}
          </div>
        </section>
      </main>
    </div>
  );
}

const root = document.getElementById('root');
if (root) {
  createRoot(root).render(<App />);
}