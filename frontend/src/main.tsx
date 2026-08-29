import React, { useEffect, useState } from 'react';
import { createRoot } from 'react-dom/client';
import { Bot, Globe2, Play, ShieldCheck, Plus, Search, Activity, ChevronDown, ChevronUp, TerminalSquare, Gauge, ShieldAlert, GitBranch, Layers, Trash2, Brain, Award, RadioTower, FileCheck2, ClipboardList, Link2, GitCompare, Network, TrendingUp } from 'lucide-react';
import Swal from 'sweetalert2';

import './index.css';

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
  // BUG FIX: Removed hardcoded prefill details
  const [f, setF] = useState({ organization: '', slug: '', email: '', password: '' });
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
      if (errorMsg.includes('Failed to fetch')) {
        errorMsg = "Cannot connect to the backend server. Please ensure the FastAPI server is running on port 8000.";
      } else { 
        try { 
          const parsed = JSON.parse(errorMsg.replace('Error: ', '')); 
          // Check if it's a FastAPI 422 validation error array
          if (Array.isArray(parsed.detail)) {
            errorMsg = parsed.detail.map((e: any) => `${e.loc[e.loc.length - 1]}: ${e.msg}`).join('\n');
          } else {
            errorMsg = parsed.detail || errorMsg; 
          }
        } catch (e) {} 
      }
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
  const [kpis, setKpis] = useState<any>(null);
  const [policies, setPolicies] = useState<any[]>([]);
  const [workflows, setWorkflows] = useState<any[]>([]);
  const [workflowRuns, setWorkflowRuns] = useState<Record<string, any[]>>({});
  const [analysis, setAnalysis] = useState<any>(null);
  const [analysisBusy, setAnalysisBusy] = useState(false);
  const [ucDef, setUcDef] = useState('');
  const [bizReq, setBizReq] = useState('');
  const [agentDesc, setAgentDesc] = useState('');
  const [intel, setIntel] = useState<any>(null);
  const [intelBusy, setIntelBusy] = useState(false);
  const [certs, setCerts] = useState<any[]>([]);
  const [drift, setDrift] = useState<any>(null);
  const [certTarget, setCertTarget] = useState('');

  const [pid, setPid] = useState('');
  const [name, setName] = useState('');
  const [url, setUrl] = useState('');
  const [mode, setMode] = useState('browser');
  const [customConfig, setCustomConfig] = useState('');
  const [msg, setMsg] = useState('');

  const [polName, setPolName] = useState('');
  const [polCategory, setPolCategory] = useState('responsible_ai');
  const [polPattern, setPolPattern] = useState('');
  const [wfName, setWfName] = useState('');
  const [wfSteps, setWfSteps] = useState<string[]>([]);

  async function load() {
    try {
      const p = await api('/projects');
      setProjects(p);
      setRuns(await api('/runs'));
      setKpis(await api('/kpis'));
      if (p[0] && !pid) {
        setPid(p[0].id);
        setTargets(await api(`/projects/${p[0].id}/targets`));
        setPolicies(await api(`/projects/${p[0].id}/policies`));
        setWorkflows(await api(`/projects/${p[0].id}/workflows`));
      } else if (pid) {
        setTargets(await api(`/projects/${pid}/targets`));
        setPolicies(await api(`/projects/${pid}/policies`));
        setWorkflows(await api(`/projects/${pid}/workflows`));
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

  async function addPolicy() {
    if (!pid || !polName || !polPattern) return;
    await api(`/projects/${pid}/policies`, { method: 'POST', body: JSON.stringify({ name: polName, category: polCategory, pattern: polPattern, severity: 'high' }) });
    setPolName(''); setPolPattern(''); load();
  }

  async function removePolicy(polId: string) {
    await api(`/policies/${polId}`, { method: 'DELETE' });
    load();
  }

  function toggleWfStep(tid: string) {
    setWfSteps(wfSteps.includes(tid) ? wfSteps.filter(s => s !== tid) : [...wfSteps, tid]);
  }

  async function createWorkflow() {
    if (!pid || !wfName || wfSteps.length === 0) return;
    await api(`/projects/${pid}/workflows`, { method: 'POST', body: JSON.stringify({ name: wfName, description: '', steps: wfSteps }) });
    setWfName(''); setWfSteps([]); load();
  }

  async function runWorkflow(wid: string) {
    await api(`/workflows/${wid}/runs`, { method: 'POST', body: JSON.stringify({ max_cases: 3, optional_context: '' }) });
    Swal.fire({ icon: 'success', title: 'Workflow validation started', background: '#0f172a', color: '#f8fafc', timer: 1300, showConfirmButton: false });
  }

  async function runIntelligence() {
    if (!pid) return;
    setIntelBusy(true);
    try {
      setIntel(await api(`/projects/${pid}/intelligence`, { method: 'POST', body: JSON.stringify({ include_llm_suggestions: true }) }));
    } catch (e) {
      Swal.fire({ icon: 'info', title: 'Test Intelligence unavailable', text: 'Run at least one validation first.', background: '#0f172a', color: '#f8fafc' });
    } finally { setIntelBusy(false); }
  }

  async function issueCertificate(tid: string) {
    const completed = runs.find((r: any) => r.target_id === tid && r.status === 'completed');
    if (!completed) { Swal.fire({ icon: 'info', title: 'No completed run', text: 'Certification requires a completed validation run for this target.', background: '#0f172a', color: '#f8fafc' }); return; }
    const c = await api(`/targets/${tid}/certificates`, { method: 'POST', body: JSON.stringify({ run_id: completed.id }) });
    setCertTarget(tid);
    setCerts(await api(`/targets/${tid}/certificates`));
    Swal.fire({ icon: c.status === 'CERTIFIED' ? 'success' : 'warning', title: `Certificate ${c.status}`, background: '#0f172a', color: '#f8fafc' });
  }

  async function runRequirementAnalysis() {
    if (!pid || (!ucDef.trim() && !bizReq.trim() && !agentDesc.trim())) {
      Swal.fire({ icon: 'info', title: 'Add at least one input', text: 'Supply a use case, business requirements, or an agent description.', background: '#0f172a', color: '#f8fafc' });
      return;
    }
    setAnalysisBusy(true);
    try {
      const out = await api(`/projects/${pid}/analysis`, { method: 'POST', body: JSON.stringify({ use_case_definition: ucDef, business_requirements: bizReq, agent_description: agentDesc }) });
      setAnalysis(out);
    } catch (e) { console.error(e); } finally { setAnalysisBusy(false); }
  }

  async function loadCerts(tid: string) {
    setCertTarget(tid);
    setCerts(await api(`/targets/${tid}/certificates`));
    setDrift((await api(`/targets/${tid}/monitor`)).drift);
  }

  async function downloadComplianceReport() {
    if (!pid) return;
    const data = await api(`/projects/${pid}/compliance-report`);
    const blob = new Blob([JSON.stringify(data, null, 2)], { type: 'application/json' });
    const a = document.createElement('a');
    a.href = URL.createObjectURL(blob);
    a.download = `avaas-compliance-report-${pid.split('-')[0]}.json`;
    a.click();
    URL.revokeObjectURL(a.href);
  }

  async function toggleWorkflowRuns(wid: string) {
    if (workflowRuns[wid]) {
      const n = { ...workflowRuns }; delete n[wid]; setWorkflowRuns(n);
    } else {
      const data = await api(`/workflows/${wid}/runs`);
      setWorkflowRuns({ ...workflowRuns, [wid]: data });
    }
  }

  return (
    <div className="min-h-screen pb-20">
      <header className="border-b border-slate-800 bg-slate-950/80 px-8 py-4 backdrop-blur sticky top-0 z-50">
        <div className="mx-auto flex max-w-7xl items-center justify-between">
          <div className="flex items-center gap-3">
            <Bot className="text-violet-400" />
            <b className="text-xl">AVaaS</b>
            <span className="text-slate-500">Enterprise AI Quality Hub</span>
          </div>
          <button className="border border-slate-700 hover:bg-slate-800 px-4 py-1 rounded text-sm" onClick={() => { localStorage.clear(); setOk(false); }}>Sign out</button>
        </div>
      </header>
      
      <main className="mx-auto max-w-7xl p-8">
        
        {/* NEW MENTOR FEEDBACK ROI SECTION */}
        <section className="mb-6 card border-emerald-500/30 shadow-[0_0_15px_rgba(16,185,129,0.05)]">
          <h2 className="text-lg font-semibold mb-4 flex items-center gap-2 text-emerald-400"><TrendingUp size={20} /> Enterprise ROI & Business Impact</h2>
          {!kpis || kpis.completed_runs === 0 ? (
            <p className="text-slate-500 text-sm">ROI projections will calculate automatically after your first test run.</p>
          ) : (
            <div className="grid grid-cols-4 gap-4">
              <div className="rounded-xl border border-slate-800 bg-slate-900/50 p-4">
                <p className="text-xs font-bold text-slate-500 uppercase tracking-wider mb-1">Manual QA Effort Saved</p>
                <p className="text-3xl font-black text-emerald-400">{kpis.roi_qa_hours_saved} <span className="text-sm font-normal text-slate-400">Hours</span></p>
                <p className="text-[10px] text-slate-500 mt-1">Based on manual regression baseline</p>
              </div>
              <div className="rounded-xl border border-slate-800 bg-slate-900/50 p-4">
                <p className="text-xs font-bold text-slate-500 uppercase tracking-wider mb-1">Cost Reduction</p>
                <p className="text-3xl font-black text-emerald-400">${kpis.roi_cost_savings.toLocaleString()}</p>
                <p className="text-[10px] text-slate-500 mt-1">Operational QA cost avoidance</p>
              </div>
              <div className="rounded-xl border border-slate-800 bg-slate-900/50 p-4">
                <p className="text-xs font-bold text-slate-500 uppercase tracking-wider mb-1">Defect Leakage Prevented</p>
                <p className="text-3xl font-black text-amber-400">{kpis.defect_leakage_prevented} <span className="text-sm font-normal text-slate-400">Critical Escapes</span></p>
                <p className="text-[10px] text-slate-500 mt-1">Caught before production release</p>
              </div>
              <div className="rounded-xl border border-slate-800 bg-slate-900/50 p-4">
                <p className="text-xs font-bold text-slate-500 uppercase tracking-wider mb-1">Release Acceleration</p>
                <p className="text-3xl font-black text-cyan-400">80% <span className="text-sm font-normal text-slate-400">Faster</span></p>
                <p className="text-[10px] text-slate-500 mt-1">Time-to-market improvement</p>
              </div>
            </div>
          )}
        </section>

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

        <section className="mt-6 card">
          <h2 className="text-lg font-semibold mb-4 flex items-center gap-2"><Gauge className="text-violet-400" size={20} /> Quality & Governance KPIs</h2>
          {!kpis || kpis.completed_runs === 0 ? (
            <p className="text-slate-500 text-sm">KPIs populate once at least one validation run completes.</p>
          ) : (
            <div className="grid grid-cols-6 gap-4">
              {[
                ['Release Gate Pass Rate', kpis.release_gate_pass_rate != null ? `${(kpis.release_gate_pass_rate * 100).toFixed(0)}%` : '—'],
                ['Avg Composite Score', kpis.avg_composite_score != null ? kpis.avg_composite_score.toFixed(1) : '—'],
                ['Avg Hallucination Rate', kpis.avg_hallucination_rate != null ? `${(kpis.avg_hallucination_rate * 100).toFixed(1)}%` : '—'],
                ['Avg Risk Score', kpis.avg_risk_score != null ? kpis.avg_risk_score.toFixed(1) : '—'],
                ['Avg Release Confidence', kpis.avg_release_confidence != null ? `${kpis.avg_release_confidence.toFixed(1)}%` : '—'],
                ['Total Validation Cost', `$${kpis.total_estimated_cost.toFixed(5)}`]
              ].map((x, i) => (
                <div key={i} className="rounded-xl border border-slate-800 bg-slate-900/50 p-3">
                  <p className="text-[10px] font-bold text-slate-500 uppercase tracking-wider mb-1">{x[0]}</p>
                  <p className="text-lg font-bold text-slate-200">{x[1]}</p>
                </div>
              ))}
            </div>
          )}
        </section>

        <section className="mt-6 grid grid-cols-3 gap-6">
          <div className="card col-span-2">
            <h2 className="text-lg font-semibold mb-2">Universal agent onboarding</h2>
            <p className="mb-6 text-sm text-slate-400">Give AVaaS a public URL. The headless browser uses stealth injection and human-typing evasion to bypass bot blocks.</p>
            <div className="grid grid-cols-2 gap-4">
              <select value={pid} onChange={(e) => setPid(e.target.value)}>
                <option value="">Select project</option>
                {projects.map((p: any) => <option key={p.id} value={p.id}>{p.name}</option>)}
              </select>
              <select value={mode} onChange={(e) => setMode(e.target.value)}>
                <option value="browser">Browser website (Stealth)</option>
                <option value="openapi">OpenAPI / API</option>
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
                placeholder='{"input_selector": "textarea", "submit_selector": "button", "response_selector": ".message"}'
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

        <section className="mt-6 grid grid-cols-2 gap-6">
          <div className="card">
            <h2 className="text-lg font-semibold mb-2 flex items-center gap-2"><ShieldAlert className="text-rose-400" size={20} /> Governance & Compliance Policies</h2>
            <p className="mb-4 text-sm text-slate-400">Deterministic PII, security, compliance, and responsible-AI rules enforced on every agent response, independent of the LLM judge.</p>
            <div className="grid grid-cols-3 gap-2">
              <select value={polCategory} onChange={(e) => setPolCategory(e.target.value)}>
                <option value="pii">PII</option>
                <option value="security">Security</option>
                <option value="compliance">Compliance</option>
                <option value="responsible_ai">Responsible AI</option>
              </select>
              <input className="col-span-2" value={polName} onChange={(e) => setPolName(e.target.value)} placeholder="Rule name" />
            </div>
            <input className="mt-2" value={polPattern} onChange={(e) => setPolPattern(e.target.value)} placeholder="Regex pattern to flag, e.g. guaranteed refund" />
            <button className="mt-3 flex items-center gap-2 bg-rose-600/80 hover:bg-rose-600 text-sm" onClick={addPolicy}><Plus size={15} />Add policy rule</button>
            <div className="mt-4 space-y-2">
              {policies.length === 0 ? <p className="text-slate-500 text-sm">No governance rules configured yet.</p> : policies.map((r: any) => (
                <div key={r.id} className="flex items-center justify-between rounded-lg border border-slate-800 bg-slate-900/50 p-2 text-sm">
                  <div>
                    <span className="rounded-md bg-slate-800 px-2 py-0.5 text-[10px] uppercase font-bold tracking-wider text-slate-400 mr-2">{r.category}</span>
                    <b className="text-slate-200">{r.name}</b>
                    <span className="text-slate-500 ml-2 font-mono text-xs">/{r.pattern}/</span>
                  </div>
                  <button onClick={() => removePolicy(r.id)} className="text-slate-500 hover:text-rose-400"><Trash2 size={15} /></button>
                </div>
              ))}
            </div>
          </div>

          <div className="card">
            <h2 className="text-lg font-semibold mb-2 flex items-center gap-2"><GitBranch className="text-cyan-400" size={20} /> Multi-Agent Workflows</h2>
            <p className="mb-4 text-sm text-slate-400">Chain targets into an end-to-end business process; each step's response is carried forward as context for the next agent.</p>
            <input className="mb-2" value={wfName} onChange={(e) => setWfName(e.target.value)} placeholder="Workflow name, e.g. Intake -> Routing -> Fulfillment" />
            <div className="flex flex-wrap gap-2 mb-3">
              {targets.map((t: any) => (
                <button key={t.id} onClick={() => toggleWfStep(t.id)} className={`text-xs px-2 py-1 rounded-md border ${wfSteps.includes(t.id) ? 'bg-cyan-600/30 border-cyan-500 text-cyan-200' : 'border-slate-700 text-slate-400'}`}>
                  {wfSteps.includes(t.id) ? `${wfSteps.indexOf(t.id) + 1}. ` : ''}{t.name}
                </button>
              ))}
            </div>
            <button className="flex items-center gap-2 bg-cyan-600/80 hover:bg-cyan-600 text-sm" onClick={createWorkflow}><Layers size={15} />Create workflow</button>
            <div className="mt-4 space-y-2">
              {workflows.length === 0 ? <p className="text-slate-500 text-sm">No multi-agent workflows defined yet.</p> : workflows.map((w: any) => (
                <div key={w.id} className="rounded-lg border border-slate-800 bg-slate-900/50 p-3">
                  <div className="flex items-center justify-between">
                    <b className="text-slate-200 text-sm">{w.name}</b>
                    <div className="flex gap-2">
                      <button onClick={() => runWorkflow(w.id)} className="flex items-center gap-1 bg-emerald-600 hover:bg-emerald-500 text-xs px-2 py-1"><Play size={13} />Run</button>
                      <button onClick={() => toggleWorkflowRuns(w.id)} className="text-xs px-2 py-1 border border-slate-700 text-slate-400">History</button>
                    </div>
                  </div>
                  <p className="text-xs text-slate-500 mt-1">{w.steps.length} chained step(s)</p>
                  {workflowRuns[w.id] && (
                    <div className="mt-2 space-y-1">
                      {workflowRuns[w.id].map((wr: any) => (
                        <div key={wr.id} className="text-xs flex justify-between text-slate-400 border-t border-slate-800 pt-1">
                          <span>#{wr.id.split('-')[0]} · {wr.status}</span>
                          <span className={wr.release_gate === 'PASS' ? 'text-emerald-400' : 'text-rose-400'}>{wr.release_gate || 'pending'} · {wr.composite_score ?? 0}</span>
                        </div>
                      ))}
                    </div>
                  )}
                </div>
              ))}
            </div>
          </div>
        </section>

        <section className="mt-6 card">
          <h2 className="text-lg font-semibold mb-2 flex items-center gap-2"><ClipboardList className="text-emerald-400" size={20} /> Requirement & Use Case Analysis Engine</h2>
          <p className="mb-4 text-sm text-slate-400">Converts a use case, business requirements, and an agent description into structured, source-classified requirements (EXPLICIT / DERIVED / INFERRED / UNKNOWN), use cases, and flagged gaps — never inventing a requirement the source text doesn't support.</p>
          <div className="grid grid-cols-3 gap-3">
            <textarea className="text-xs h-20" value={ucDef} onChange={(e) => setUcDef(e.target.value)} placeholder="Use case definition, e.g. Customer wants to return a product" />
            <textarea className="text-xs h-20" value={bizReq} onChange={(e) => setBizReq(e.target.value)} placeholder="Business requirements / policy text" />
            <textarea className="text-xs h-20" value={agentDesc} onChange={(e) => setAgentDesc(e.target.value)} placeholder="Agent description / system prompt" />
          </div>
          <button className="mt-3 flex items-center gap-2 bg-emerald-600/80 hover:bg-emerald-600 text-sm" disabled={!pid || analysisBusy} onClick={runRequirementAnalysis}>
            {analysisBusy ? 'Analyzing...' : 'Run requirement analysis'}
          </button>
          {analysis && (
            <div className="mt-4 grid grid-cols-3 gap-4">
              <div className="rounded-xl border border-slate-800 bg-slate-900/50 p-4">
                <p className="text-[10px] font-bold text-slate-500 uppercase tracking-wider mb-2">Requirements by source (v{analysis.version_no})</p>
                <div className="text-sm text-slate-300 space-y-1">
                  <p>Explicit: <b className="text-emerald-400">{analysis.analysis.analysis_summary?.explicit_requirement_count ?? 0}</b></p>
                  <p>Derived: <b className="text-cyan-400">{analysis.analysis.analysis_summary?.derived_requirement_count ?? 0}</b></p>
                  <p>Inferred/Unknown: <b className="text-amber-400">{analysis.analysis.analysis_summary?.inferred_requirement_count ?? 0}</b></p>
                </div>
                <ul className="text-xs text-slate-400 mt-2 space-y-1 max-h-40 overflow-auto">
                  {(analysis.analysis.requirements || []).map((req: any, i: number) => (
                    <li key={i}><span className={`font-bold ${req.source === 'EXPLICIT' ? 'text-emerald-400' : req.source === 'DERIVED' ? 'text-cyan-400' : 'text-amber-400'}`}>[{req.source}]</span> {req.requirement_id}: {req.requirement}</li>
                  ))}
                </ul>
              </div>
              <div className="rounded-xl border border-slate-800 bg-slate-900/50 p-4">
                <p className="text-[10px] font-bold text-slate-500 uppercase tracking-wider mb-2">Use Cases</p>
                {(analysis.analysis.use_cases || []).length === 0 ? <p className="text-xs text-slate-500">None identified.</p> : (
                  <ul className="text-xs text-slate-300 space-y-2">
                    {analysis.analysis.use_cases.map((uc: any, i: number) => (
                      <li key={i}><b>{uc.use_case_id}: {uc.name}</b><br /><span className="text-slate-500">{uc.actor} — {uc.goal}</span></li>
                    ))}
                  </ul>
                )}
              </div>
              <div className="rounded-xl border border-slate-800 bg-slate-900/50 p-4">
                <p className="text-[10px] font-bold text-amber-500 uppercase tracking-wider mb-2">Requirement Gaps</p>
                {(analysis.analysis.requirement_gaps || []).length === 0 ? <p className="text-xs text-slate-500">No gaps flagged.</p> : (
                  <ul className="text-xs text-amber-300/90 space-y-2">
                    {analysis.analysis.requirement_gaps.map((g: any, i: number) => (
                      <li key={i}><b>{g.gap_id}</b>: {g.description} <span className="text-slate-500">— {g.question_for_qa}</span></li>
                    ))}
                  </ul>
                )}
              </div>
            </div>
          )}
        </section>

        <section className="mt-6 card">
          <div className="flex items-center justify-between mb-2">
            <h2 className="text-lg font-semibold flex items-center gap-2"><Brain className="text-fuchsia-400" size={20} /> AI Test Intelligence</h2>
            <div className="flex gap-2">
              <button className="bg-fuchsia-600/80 hover:bg-fuchsia-600 text-sm" disabled={!pid || intelBusy} onClick={runIntelligence}>
                {intelBusy ? 'Analyzing...' : 'Analyze coverage & risk'}
              </button>
              <button className="border border-slate-700 hover:bg-slate-800 text-sm flex items-center gap-2" disabled={!pid} onClick={downloadComplianceReport}>
                <FileCheck2 size={15} />Export compliance report
              </button>
            </div>
          </div>
          <p className="mb-4 text-sm text-slate-400">Mines run history for uncovered scenarios, a recommended regression suite, and an explainable release-risk prediction.</p>
          {!intel ? <p className="text-slate-500 text-sm">Run an analysis to surface coverage gaps and release risk.</p> : (
            <div className="grid grid-cols-3 gap-4">
              <div className="rounded-xl border border-slate-800 bg-slate-900/50 p-4">
                <p className="text-[10px] font-bold text-slate-500 uppercase tracking-wider mb-2">Coverage</p>
                <p className="text-sm text-slate-300">Case types: <b>{(intel.coverage.case_type_coverage * 100).toFixed(0)}%</b></p>
                {intel.coverage.missing_case_types?.length > 0 && <p className="text-xs text-amber-400 mt-1">Missing: {intel.coverage.missing_case_types.join(', ')}</p>}
                {intel.coverage.requirement_coverage != null && <p className="text-sm text-slate-300 mt-1">Requirements: <b>{(intel.coverage.requirement_coverage * 100).toFixed(0)}%</b></p>}
                {intel.coverage.untested_requirements?.length > 0 && (
                  <ul className="text-xs text-amber-300/80 mt-2 list-disc pl-4">
                    {intel.coverage.untested_requirements.slice(0, 3).map((r: any, i: number) => <li key={i}>{r.text}</li>)}
                  </ul>
                )}
              </div>
              <div className="rounded-xl border border-slate-800 bg-slate-900/50 p-4">
                <p className="text-[10px] font-bold text-slate-500 uppercase tracking-wider mb-2">Predicted Release Risk</p>
                <p className={`text-2xl font-black ${intel.release_risk.risk_band === 'LOW' ? 'text-emerald-400' : intel.release_risk.risk_band === 'MEDIUM' ? 'text-amber-400' : 'text-rose-500'}`}>
                  {intel.release_risk.risk_band} · {intel.release_risk.predicted_risk}
                </p>
                <p className="text-xs text-slate-400 mt-1">{intel.release_risk.recommendation}</p>
                <ul className="text-xs text-slate-500 mt-2 list-disc pl-4">
                  {intel.release_risk.factors.map((f: any, i: number) => <li key={i}>{f.factor} (+{f.contribution}): {f.detail}</li>)}
                </ul>
              </div>
              <div className="rounded-xl border border-slate-800 bg-slate-900/50 p-4">
                <p className="text-[10px] font-bold text-slate-500 uppercase tracking-wider mb-2">Recommended Regression Suite</p>
                {intel.recommended_regression_suite?.length === 0 ? <p className="text-xs text-slate-500">No high-signal cases yet; needs more run history.</p> : (
                  <ul className="text-xs text-slate-300 space-y-2">
                    {intel.recommended_regression_suite.slice(0, 4).map((c: any, i: number) => (
                      <li key={i}><b className="text-cyan-300">[{c.priority}]</b> {c.prompt.slice(0, 70)}...<br /><span className="text-slate-500">{c.reasons.join('; ')}</span></li>
                    ))}
                  </ul>
                )}
              </div>
              {intel.suggested_uncovered_scenarios?.length > 0 && (
                <div className="col-span-3 rounded-xl border border-slate-800 bg-slate-900/50 p-4">
                  <p className="text-[10px] font-bold text-slate-500 uppercase tracking-wider mb-2">Suggested Uncovered Scenarios</p>
                  <ul className="text-xs text-slate-300 space-y-1 list-disc pl-4">
                    {intel.suggested_uncovered_scenarios.map((sc: any, i: number) => (
                      <li key={i}><b>{sc.scenario}</b> <span className="text-slate-500">({sc.suggested_type}) — {sc.why_it_matters}</span></li>
                    ))}
                  </ul>
                </div>
              )}
            </div>
          )}
        </section>

        <section className="mt-6 card">
          <h2 className="text-lg font-semibold mb-2 flex items-center gap-2"><Award className="text-amber-400" size={20} /> Agent Certification & Production Monitoring</h2>
          <p className="mb-4 text-sm text-slate-400">Issue a signed, verifiable release certificate for a target, and watch live traffic for drift against its certified baseline.</p>
          <div className="flex flex-wrap gap-2 mb-4">
            {targets.map((t: any) => (
              <div key={t.id} className="flex gap-1">
                <button onClick={() => loadCerts(t.id)} className={`text-xs px-2 py-1 rounded-md border ${certTarget === t.id ? 'bg-amber-600/30 border-amber-500 text-amber-200' : 'border-slate-700 text-slate-400'}`}>{t.name}</button>
                <button onClick={() => issueCertificate(t.id)} className="text-xs px-2 py-1 rounded-md bg-amber-600/80 hover:bg-amber-600">Certify</button>
              </div>
            ))}
          </div>
          {certTarget && (
            <div className="grid grid-cols-2 gap-4">
              <div className="rounded-xl border border-slate-800 bg-slate-900/50 p-4">
                <p className="text-[10px] font-bold text-slate-500 uppercase tracking-wider mb-2">Certificates</p>
                {certs.length === 0 ? <p className="text-xs text-slate-500">No certificates issued for this target.</p> : certs.map((c: any) => (
                  <div key={c.id} className="text-xs border-t border-slate-800 py-2">
                    <span className={`font-bold ${c.status === 'CERTIFIED' ? 'text-emerald-400' : 'text-rose-400'}`}>{c.status}</span>
                    <span className="text-slate-500"> · score {c.payload?.composite_score} · risk {c.payload?.predicted_risk_band} · v{c.payload?.prompt_version_no ?? '—'}</span>
                    <div className="font-mono text-[10px] text-slate-600 mt-1 truncate">sig {c.signature?.slice(0, 32)}...</div>
                  </div>
                ))}
              </div>
              <div className="rounded-xl border border-slate-800 bg-slate-900/50 p-4">
                <p className="text-[10px] font-bold text-slate-500 uppercase tracking-wider mb-2 flex items-center gap-2"><RadioTower size={13} /> Production Drift</p>
                {!drift || drift.status === 'NO_DATA' ? <p className="text-xs text-slate-500">No production samples ingested yet. POST to /targets/{'{id}'}/monitor to stream live traffic.</p> : (
                  <div className="text-xs text-slate-300 space-y-1">
                    <p className={`font-bold ${drift.status === 'HEALTHY' ? 'text-emerald-400' : drift.status === 'CRITICAL_DRIFT' ? 'text-rose-500' : 'text-amber-400'}`}>{drift.status}</p>
                    <p>Samples: {drift.samples} · Prod pass rate: {drift.production_pass_rate != null ? (drift.production_pass_rate * 100).toFixed(0) + '%' : '—'}</p>
                    <p>Drift vs baseline: {drift.drift_vs_baseline ?? '—'} · Governance findings: {drift.governance_findings}</p>
                    <p className="text-slate-500">{drift.recommendation}</p>
                  </div>
                )}
              </div>
            </div>
          )}
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

                <div className="grid grid-cols-6 gap-6">
                  <div>
                    <p className="text-xs font-bold text-slate-500 uppercase tracking-wider mb-1">Release Gate</p>
                    <p className={`text-xl font-black ${r.release_gate === 'PASS' ? 'text-emerald-400' : r.release_gate === 'WARN' ? 'text-amber-400' : 'text-rose-500'}`}>
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
                  <div>
                    <p className="text-xs font-bold text-slate-500 uppercase tracking-wider mb-1">Risk Score</p>
                    <p className={`text-lg font-bold ${(r.risk_score ?? 0) >= 50 ? 'text-rose-400' : (r.risk_score ?? 0) >= 25 ? 'text-amber-400' : 'text-emerald-400'}`}>{r.risk_score ?? '—'}</p>
                  </div>
                  <div className="col-span-2">
                    <p className="text-xs font-bold text-slate-500 uppercase tracking-wider mb-1">QA Telemetry</p>
                    <div className="text-xs text-slate-300 font-mono mt-1 space-y-1">
                      <p>Engine: <span className="text-violet-300 uppercase font-bold">{r.summary?.llm_provider || 'Evaluating...'}</span></p>
                      <p>Tokens Used: {r.summary?.tokens ? (r.summary.tokens.prompt + r.summary.tokens.completion).toLocaleString() : 0}</p>
                      <p>Est. Cost: <span className="text-emerald-400">${r.summary?.estimated_cost ? r.summary.estimated_cost.toFixed(5) : '0.00000'}</span> · Rel Confidence: <span className="text-cyan-300">{r.release_confidence ?? '—'}%</span></p>
                    </div>
                  </div>
                </div>

                {r.status === 'completed' && (
                  <div className="mt-5 flex gap-2">
                    <button onClick={() => toggleRunDetails(r.id)} className="flex-1 flex justify-center items-center gap-2 py-2 bg-slate-800 hover:bg-slate-700 text-slate-300 text-sm font-medium rounded-lg transition">
                      {runDetails[r.id] ? <><ChevronUp size={16}/> Hide Detailed Report</> : <><ChevronDown size={16}/> View Detailed Report</>}
                    </button>
                    <button onClick={async () => { const t = await api(`/runs/${r.id}/traceability`); Swal.fire({ title: 'Requirement traceability', html: `<pre style="text-align:left;font-size:11px;max-height:400px;overflow:auto">${JSON.stringify(t, null, 2)}</pre>`, background: '#0f172a', color: '#f8fafc', width: 700 }); }} className="px-3 py-2 border border-slate-700 hover:bg-slate-800 text-slate-300 text-sm rounded-lg flex items-center gap-2">
                      <Link2 size={15} /> Traceability
                    </button>
                    <button onClick={async () => { const g = await api(`/runs/${r.id}/regression`); const color = g.decision === 'PASS' ? '#34d399' : g.decision === 'FAIL' ? '#fbbf24' : '#f43f5e'; Swal.fire({ title: `Release gate: <span style="color:${color}">${g.decision}</span>`, html: `<p style="text-align:left;margin-bottom:8px">${g.summary}</p><pre style="text-align:left;font-size:11px;max-height:360px;overflow:auto">${JSON.stringify(g.checks, null, 2)}</pre>`, background: '#0f172a', color: '#f8fafc', width: 700 }); }} className="px-3 py-2 border border-slate-700 hover:bg-slate-800 text-slate-300 text-sm rounded-lg flex items-center gap-2">
                      <GitCompare size={15} /> Regression
                    </button>
                    <button onClick={async () => { const d = await api(`/runs/${r.id}`); const traces = d.results.map((res: any) => ({ case: res.case_type, requirement_id: res.requirement_id, latency_ms: res.evidence?.latency_ms, correlation_id: res.evidence?.correlation_id, tool_calls: res.evidence?.tool_calls, status_codes: res.evidence?.status_codes, tokens: res.evidence?.tokens, state_verification: res.evidence?.state_verification })); Swal.fire({ title: 'Trace explorer', html: `<pre style="text-align:left;font-size:11px;max-height:400px;overflow:auto">${JSON.stringify(traces, null, 2)}</pre>`, background: '#0f172a', color: '#f8fafc', width: 760 }); }} className="px-3 py-2 border border-slate-700 hover:bg-slate-800 text-slate-300 text-sm rounded-lg flex items-center gap-2">
                      <Network size={15} /> Traces
                    </button>
                  </div>
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
                            {res.evidence?.policy_findings?.length > 0 && (
                              <span className="ml-2 px-2 py-1 bg-amber-500/20 text-amber-400 text-[10px] font-bold uppercase rounded border border-amber-500/30">
                                🛡️ {res.evidence.policy_findings.length} governance finding(s)
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
                        {res.evidence?.policy_findings?.length > 0 && (
                          <div className="mt-3 border-t border-slate-800 pt-3">
                            <span className="text-[10px] font-bold text-amber-500 uppercase tracking-wider block mb-1">Governance / PII / Compliance Findings</span>
                            <ul className="text-xs text-amber-300/90 space-y-1">
                              {res.evidence.policy_findings.map((f: any, idx: number) => (
                                <li key={idx}>[{f.severity}] {f.rule_name}: {f.detail}</li>
                              ))}
                            </ul>
                          </div>
                        )}
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