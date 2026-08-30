import streamlit as st
import requests
import json
import time

# --- CONFIGURATION ---
st.set_page_config(page_title="AVaaS Enterprise", page_icon="🛡️", layout="wide", initial_sidebar_state="expanded")
API_URL = "http://127.0.0.1:8000/api/v1"

# --- PREMIUM ENTERPRISE DARK CSS ---
st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap');
    .stApp { background-color: #020617; font-family: 'Inter', sans-serif; }
    [data-testid="stSidebar"] { background-color: #0f172a; border-right: 1px solid #1e293b; }
    #MainMenu, footer, header {visibility: hidden;}
    .block-container { padding-top: 2rem !important; max-width: 95% !important; }
    h1, h2, h3 { color: #f8fafc !important; font-weight: 700 !important; letter-spacing: -0.02em; }
    p, span, div { color: #cbd5e1; }
    
    .stTextInput input, .stTextArea textarea, .stSelectbox div[data-baseweb="select"] {
        background-color: #0f172a !important; border: 1px solid #334155 !important; color: #f8fafc !important; border-radius: 8px; font-size: 14px;
    }
    .stTextInput input:focus, .stTextArea textarea:focus { border-color: #8b5cf6 !important; box-shadow: 0 0 0 1px #8b5cf6 !important; }
    
    div.stButton > button { border-radius: 8px !important; font-weight: 600 !important; transition: all 0.2s ease-in-out; }
    div.stButton > button[kind="primary"] { background: linear-gradient(135deg, #8b5cf6 0%, #6d28d9 100%) !important; border: none !important; color: white !important; box-shadow: 0 4px 12px rgba(139, 92, 246, 0.2); }
    div.stButton > button[kind="primary"]:hover { box-shadow: 0 6px 16px rgba(139, 92, 246, 0.4); transform: translateY(-1px); }
    div.stButton > button[kind="secondary"] { background-color: #1e293b !important; border: 1px solid #334155 !important; color: #e2e8f0 !important; }
    
    .dashboard-card { background-color: #0f172a; border: 1px solid #1e293b; border-radius: 12px; padding: 24px; box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.2); transition: transform 0.2s; }
    .dashboard-card:hover { transform: translateY(-2px); box-shadow: 0 10px 15px -3px rgba(0, 0, 0, 0.3); border-color: #334155; }
    .card-title { color: #94a3b8; font-size: 11px; font-weight: 700; text-transform: uppercase; letter-spacing: 0.05em; margin-bottom: 8px; }
    .card-value { font-size: 32px; font-weight: 800; line-height: 1.2; letter-spacing: -0.02em; }
    .card-value.emerald { color: #34d399; text-shadow: 0 0 20px rgba(52, 211, 153, 0.2); }
    .card-value.blue { color: #38bdf8; text-shadow: 0 0 20px rgba(56, 189, 248, 0.2); }
    .card-value.amber { color: #fbbf24; text-shadow: 0 0 20px rgba(251, 191, 36, 0.2); }
    
    .stTabs [data-baseweb="tab-list"] { gap: 2.5rem; border-bottom: 1px solid #1e293b; padding-bottom: 5px; }
    .stTabs [data-baseweb="tab"] { background: transparent !important; border: none !important; color: #64748b !important; font-weight: 600; font-size: 15px; padding: 10px 0; }
    .stTabs [aria-selected="true"] { color: #a78bfa !important; border-bottom: 3px solid #8b5cf6 !important; }
    
    div[data-testid="stMetricValue"] { color: #f8fafc !important; font-weight: 800 !important; font-size: 28px !important; }
    div[data-testid="stMetricLabel"] { color: #94a3b8 !important; font-weight: 700 !important; text-transform: uppercase; font-size: 11px !important; letter-spacing: 0.05em; }
    div[data-testid="stVerticalBlockBorderWrapper"] > div { border-radius: 12px !important; border: 1px solid #1e293b !important; background-color: #0f172a !important; }
</style>
""", unsafe_allow_html=True)

if "access_token" not in st.session_state: st.session_state.access_token = None
if "refresh_token" not in st.session_state: st.session_state.refresh_token = None
if "pid" not in st.session_state: st.session_state.pid = None

def api(endpoint, method="GET", data=None, suppress_404=False, is_retry=False):
    headers = {"Content-Type": "application/json"}
    if st.session_state.access_token: headers["Authorization"] = f"Bearer {st.session_state.access_token}"
    url = f"{API_URL}{endpoint}"
    response = None
    try:
        if method == "GET": response = requests.get(url, headers=headers)
        elif method == "POST": response = requests.post(url, headers=headers, json=data)
        elif method == "DELETE": response = requests.delete(url, headers=headers)
            
        if response.status_code == 401 and not is_retry and st.session_state.refresh_token:
            refresh_res = requests.post(f"{API_URL}/auth/refresh", json={"refresh_token": st.session_state.refresh_token})
            if refresh_res.status_code == 200:
                new_tokens = refresh_res.json()
                st.session_state.access_token = new_tokens["access_token"]
                st.session_state.refresh_token = new_tokens["refresh_token"]
                return api(endpoint, method, data, suppress_404, is_retry=True)
                
        if response.status_code in [401, 403]:
            st.session_state.access_token = None
            st.error("Session expired. Please sign in again.")
            st.rerun()
            
        if response.status_code == 404 and suppress_404: return None
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        err_msg = str(e)
        if response is not None and response.text:
            try:
                parsed = response.json()
                err_msg = "\n".join([f"{err['loc'][-1]}: {err['msg']}" for err in parsed["detail"]]) if isinstance(parsed.get("detail"), list) else parsed.get("detail", response.text)
            except: err_msg = response.text
        st.error(f"API Error: {err_msg}")
        return None

# --- DIALOG MODALS ---
@st.dialog("Requirement Traceability")
def show_traceability(run_id):
    data = api(f"/runs/{run_id}/traceability")
    if data:
        st.json(data)

@st.dialog("Release Gate Decision")
def show_regression(run_id):
    data = api(f"/runs/{run_id}/regression")
    if data:
        decision = data.get("decision", "FAIL")
        color = "#34d399" if decision == "PASS" else "#fbbf24" if decision == "WARN" else "#f43f5e"
        st.markdown(f"### Decision: <span style='color:{color}'>{decision}</span>", unsafe_allow_html=True)
        st.markdown(f"**Summary:** {data.get('summary', 'Evaluation completed.')}")
        st.json(data.get('checks', []))

@st.dialog("Network Traces Explorer")
def show_traces(run_id):
    d = api(f"/runs/{run_id}")
    if d and "results" in d:
        traces = [{
            "case": res["case_type"],
            "requirement_id": res["requirement_id"],
            "latency_ms": res.get("evidence", {}).get("latency_ms"),
            "correlation_id": res.get("evidence", {}).get("correlation_id"),
            "tool_calls": res.get("evidence", {}).get("tool_calls"),
            "status_codes": res.get("evidence", {}).get("status_codes"),
            "tokens": res.get("evidence", {}).get("tokens"),
            "state_verification": res.get("evidence", {}).get("state_verification")
        } for res in d["results"]]
        st.json(traces)

# --- AUTHENTICATION VIEW ---
def auth_view():
    st.markdown("<br><br><br>", unsafe_allow_html=True)
    col1, col2, col3 = st.columns([1, 1.2, 1])
    with col2:
        st.markdown("<div style='text-align: center; margin-bottom: 2rem;'><div style='font-size: 3rem; margin-bottom: 10px;'>🛡️</div><h1 style='color: #f8fafc; font-size: 2.5rem; font-weight: 800; letter-spacing: -0.03em;'>AVaaS Enterprise</h1><p style='color: #94a3b8; font-size: 1.1rem;'>AI Quality Engineering & Governance Platform</p></div>", unsafe_allow_html=True)
        tab1, tab2 = st.tabs(["Sign In", "Create Organization"])
        with tab1:
            with st.container(border=True):
                with st.form("login_form", clear_on_submit=False):
                    slug = st.text_input("Tenant Slug", placeholder="acme-corp")
                    email = st.text_input("Email", placeholder="admin@example.com")
                    password = st.text_input("Password", type="password")
                    st.markdown("<br>", unsafe_allow_html=True)
                    if st.form_submit_button("Access Workspace", type="primary", use_container_width=True):
                        res = api("/auth/login", method="POST", data={"tenant_slug": slug, "email": email, "password": password})
                        if res:
                            st.session_state.access_token = res["access_token"]; st.session_state.refresh_token = res["refresh_token"]; st.rerun()
        with tab2:
            with st.container(border=True):
                with st.form("register_form", clear_on_submit=False):
                    org = st.text_input("Organization Name", placeholder="Acme Corp")
                    slug = st.text_input("Tenant Slug", placeholder="acme-corp")
                    email = st.text_input("Email", placeholder="admin@example.com")
                    password = st.text_input("Password", type="password", help="Must be at least 12 characters")
                    st.markdown("<br>", unsafe_allow_html=True)
                    if st.form_submit_button("Register Organization", type="primary", use_container_width=True):
                        res = api("/auth/register", method="POST", data={"organization": org, "slug": slug, "email": email, "password": password})
                        if res:
                            st.session_state.access_token = res["access_token"]; st.session_state.refresh_token = res["refresh_token"]; st.rerun()

# --- MAIN DASHBOARD VIEW ---
def main_dashboard():
    projects = api("/projects") or []
    runs = api("/runs") or []
    kpis = api("/kpis") or {}
    
    with st.sidebar:
        st.markdown("<h2 style='color: #f8fafc; margin-bottom: 0;'>AVaaS</h2><p style='color:#8b5cf6; font-size:11px; font-weight:800; letter-spacing:1.5px;'>CONTROL PLANE</p>", unsafe_allow_html=True)
        st.divider()
        if projects:
            project_options = {p["id"]: p["name"] for p in projects}
            if not st.session_state.pid or st.session_state.pid not in project_options: st.session_state.pid = list(project_options.keys())[0]
            selected_pid = st.selectbox("Active Workspace", options=list(project_options.keys()), format_func=lambda x: project_options[x], index=list(project_options.keys()).index(st.session_state.pid))
            if selected_pid != st.session_state.pid: st.session_state.pid = selected_pid; st.rerun()
        st.markdown("<br>", unsafe_allow_html=True)
        with st.expander("➕ Create New Project", expanded=not projects):
            with st.form("new_proj_form", clear_on_submit=True):
                pname = st.text_input("Project Name")
                if st.form_submit_button("Create", type="primary", use_container_width=True):
                    api("/projects", method="POST", data={"name": pname, "description": ""}); st.rerun()
        st.divider()
        st.markdown("<h4 style='color:#f8fafc; font-size:13px; font-weight:700; text-transform:uppercase;'>Global Telemetry</h4>", unsafe_allow_html=True)
        st.metric("Total Executions", len(runs))
        st.metric("Passed Gates", len([r for r in runs if r.get("release_gate") == "PASS"]))
        st.divider()
        if st.button("Sign Out", use_container_width=True): st.session_state.access_token = None; st.rerun()

    if not projects: st.info("👋 Welcome to AVaaS! Please create a new project in the sidebar to begin."); return

    targets = api(f"/projects/{st.session_state.pid}/targets") or []
    policies = api(f"/projects/{st.session_state.pid}/policies") or []
    workflows = api(f"/projects/{st.session_state.pid}/workflows") or []

    t_roi, t_target, t_gov, t_intel, t_cert, t_runs = st.tabs(["📈 Dashboard & ROI", "🎯 Targets & Agents", "🛡️ Governance Rules", "🧠 Test Intelligence", "🏅 Certification", "📊 Trace Explorer"])

    with t_roi:
        st.markdown("<h3 style='margin-bottom: 1.5rem;'>Business Impact & ROI</h3>", unsafe_allow_html=True)
        if kpis.get("completed_runs", 0) == 0: st.info("Execute a QA pipeline on a target to generate automated ROI and Quality metrics.")
        else:
            col1, col2, col3, col4 = st.columns(4)
            col1.markdown(f"<div class='dashboard-card'><div class='card-title'>QA EFFORT SAVED</div><div class='card-value emerald'>{kpis.get('roi_qa_hours_saved', 0)} <span style='font-size:16px; color:#94a3b8; font-weight:600;'>Hours</span></div></div>", unsafe_allow_html=True)
            col2.markdown(f"<div class='dashboard-card'><div class='card-title'>COST REDUCTION</div><div class='card-value emerald'>${kpis.get('roi_cost_savings', 0):,}</div></div>", unsafe_allow_html=True)
            col3.markdown(f"<div class='dashboard-card'><div class='card-title'>DEFECTS PREVENTED</div><div class='card-value amber'>{kpis.get('defect_leakage_prevented', 0)} <span style='font-size:16px; color:#94a3b8; font-weight:600;'>Escapes</span></div></div>", unsafe_allow_html=True)
            col4.markdown("<div class='dashboard-card'><div class='card-title'>RELEASE VELOCITY</div><div class='card-value blue'>80% <span style='font-size:16px; color:#94a3b8; font-weight:600;'>Faster</span></div></div>", unsafe_allow_html=True)
            st.markdown("<h3 style='margin-top: 2.5rem; margin-bottom: 1.5rem;'>Quality Assurance KPIs</h3>", unsafe_allow_html=True)
            k1, k2, k3, k4, k5 = st.columns(5)
            k1.markdown(f"<div class='dashboard-card' style='padding:18px;'><div class='card-title'>GATE PASS RATE</div><div style='color:#f8fafc; font-size:24px; font-weight:700;'>{int(kpis.get('release_gate_pass_rate', 0)*100)}%</div></div>", unsafe_allow_html=True)
            k2.markdown(f"<div class='dashboard-card' style='padding:18px;'><div class='card-title'>AVG COMPOSITE</div><div style='color:#f8fafc; font-size:24px; font-weight:700;'>{kpis.get('avg_composite_score', 0)}</div></div>", unsafe_allow_html=True)
            k3.markdown(f"<div class='dashboard-card' style='padding:18px;'><div class='card-title'>HALLUCINATIONS</div><div style='color:#f8fafc; font-size:24px; font-weight:700;'>{kpis.get('avg_hallucination_rate', 0)*100:.1f}%</div></div>", unsafe_allow_html=True)
            k4.markdown(f"<div class='dashboard-card' style='padding:18px;'><div class='card-title'>AVG RISK SCORE</div><div style='color:#f8fafc; font-size:24px; font-weight:700;'>{kpis.get('avg_risk_score', 0)}</div></div>", unsafe_allow_html=True)
            k5.markdown(f"<div class='dashboard-card' style='padding:18px;'><div class='card-title'>COST PER RUN</div><div style='color:#f8fafc; font-size:24px; font-weight:700;'>${kpis.get('total_estimated_cost', 0):.5f}</div></div>", unsafe_allow_html=True)

    with t_target:
        st.markdown("<h3 style='margin-bottom: 1rem;'>Agent Registration</h3>", unsafe_allow_html=True)
        with st.container(border=True):
            with st.form("discover_form", clear_on_submit=False):
                col1, col2, col3 = st.columns([1, 2, 1])
                t_mode = col1.selectbox("Ingestion Mode", ["browser", "openapi", "rest"])
                t_url = col2.text_input("Target URL", placeholder="https://agent.example.com")
                t_name = col3.text_input("Friendly Name (Optional)")
                with st.expander("Advanced Selector Configuration (Optional)"):
                    t_config = st.text_area("JSON Config", placeholder='{"input_selector": "textarea"}', height=100)
                if st.form_submit_button("Connect & Discover Target", type="primary"):
                    parsed_config = {}
                    if t_config:
                        try: parsed_config = json.loads(t_config)
                        except: st.error("Invalid JSON"); st.stop()
                    res = api(f"/projects/{st.session_state.pid}/targets", "POST", {"name": t_name or t_url.split("//")[-1], "base_url": t_url, "mode": t_mode, "config": parsed_config})
                    if res:
                        with st.spinner("Connecting via Playwright stealth engine..."):
                            disc = api(f"/targets/{res['id']}/discover", "POST")
                            if disc and disc.get("ready"): st.success("Target successfully connected and inputs verified.")
                            else: st.info("Target registered. Utilizing custom selectors if provided.")
                            time.sleep(1); st.rerun()

        st.markdown("<h3 style='margin-top: 2.5rem; margin-bottom: 1rem;'>Active Targets</h3>", unsafe_allow_html=True)
        if not targets: st.info("No targets registered. Add a URL above to begin testing.")
        for t in targets:
            with st.container(border=True):
                col1, col2 = st.columns([4, 1])
                col1.markdown(f"**{t['name']}** &nbsp; <span style='font-size:10px; background:#0f172a; color:#a78bfa; padding:3px 8px; border-radius:12px; border: 1px solid #334155; font-weight:700;'>{t['mode'].upper()}</span><br><span style='color:#94a3b8; font-size:13px;'>{t['base_url']}</span>", unsafe_allow_html=True)
                if col2.button("▶ Execute QA Pipeline", key=f"run_{t['id']}", type="primary", use_container_width=True):
                    api(f"/targets/{t['id']}/runs", "POST", {"max_cases": 3, "optional_context": ""})
                    st.toast("Pipeline Initialized!", icon="🚀"); time.sleep(0.5); st.rerun()

    with t_gov:
        col1, col2 = st.columns(2, gap="large")
        with col1:
            st.markdown("### Safety & Compliance Policies")
            with st.container(border=True):
                with st.form("policy_form", clear_on_submit=True):
                    cat = st.selectbox("Category", ["pii", "security", "compliance", "responsible_ai"])
                    p_name = st.text_input("Rule Name")
                    p_pat = st.text_input("Regex Pattern")
                    if st.form_submit_button("Add Policy Rule", type="primary", use_container_width=True):
                        api(f"/projects/{st.session_state.pid}/policies", "POST", {"name": p_name, "category": cat, "pattern": p_pat, "severity": "high"}); st.rerun()
            for pol in policies:
                st.markdown(f"<div class='dashboard-card' style='padding: 16px; margin-bottom: 12px;'><span style='font-size:10px; background:#ef444420; color:#f87171; padding:3px 8px; border-radius:12px; font-weight:700;'>{pol['category'].upper()}</span> <b style='color:#f8fafc; margin-left:8px; font-size:14px;'>{pol['name']}</b><br><code style='color:#cbd5e1; background:transparent; font-size:13px; display:block; margin-top:8px;'>/{pol['pattern']}/</code></div>", unsafe_allow_html=True)
        with col2:
            st.markdown("### Multi-Agent Workflows")
            with st.container(border=True):
                with st.form("wf_form", clear_on_submit=True):
                    w_name = st.text_input("Workflow Name")
                    w_steps = st.multiselect("Select Targets in Execution Order", options=[t["id"] for t in targets], format_func=lambda x: next(t["name"] for t in targets if t["id"] == x))
                    if st.form_submit_button("Create Workflow", type="primary", use_container_width=True):
                        api(f"/projects/{st.session_state.pid}/workflows", "POST", {"name": w_name, "steps": w_steps}); st.rerun()
            for wf in workflows:
                with st.container(border=True):
                    wf_col1, wf_col2 = st.columns([3, 1])
                    wf_col1.markdown(f"<b style='color:#f8fafc; font-size:15px;'>{wf['name']}</b><br><span style='color:#94a3b8; font-size:13px;'>{len(wf.get('steps',[]))} execution steps</span>", unsafe_allow_html=True)
                    if wf_col2.button("▶ Run", key=f"rwf_{wf['id']}", type="primary", use_container_width=True):
                        api(f"/workflows/{wf['id']}/runs", "POST", {"max_cases": 3}); st.toast("Workflow started!", icon="🚀")

    with t_intel:
        st.markdown("### Requirements Engine")
        with st.container(border=True):
            with st.form("req_form"):
                rc1, rc2, rc3 = st.columns(3)
                uc = rc1.text_area("Use Case Definition", height=150)
                br = rc2.text_area("Business Rules / Policy", height=150)
                ad = rc3.text_area("System Prompt / Agent Persona", height=150)
                if st.form_submit_button("Execute Semantic Analysis", type="primary"):
                    with st.spinner("Parsing logic via LLM..."):
                        api(f"/projects/{st.session_state.pid}/analysis", "POST", {"use_case_definition": uc, "business_requirements": br, "agent_description": ad}); st.rerun()
        analysis = api(f"/projects/{st.session_state.pid}/analysis/latest", suppress_404=True)
        if analysis and "analysis" in analysis:
            ac1, ac2, ac3 = st.columns(3)
            with ac1:
                with st.container(border=True):
                    st.markdown("**Requirements Hierarchy**")
                    for req in analysis['analysis'].get('requirements', []):
                        color = "#10b981" if req['source'] == "EXPLICIT" else "#3b82f6" if req['source'] == "DERIVED" else "#f59e0b"
                        st.markdown(f"<span style='color:{color}; font-size:11px; font-weight:bold;'>[{req['source']}]</span> <span style='font-size:14px; color:#cbd5e1;'>{req['requirement_id']}: {req['requirement']}</span>", unsafe_allow_html=True)
            with ac2:
                with st.container(border=True):
                    st.markdown("**Identified Use Cases**")
                    for u in analysis['analysis'].get('use_cases', []):
                        st.markdown(f"<span style='font-size:14px; color:#cbd5e1;'>**{u['use_case_id']}**: {u['name']}</span>", unsafe_allow_html=True)
            with ac3:
                with st.container(border=True):
                    st.markdown("**Security & Logic Gaps**")
                    for g in analysis['analysis'].get('requirement_gaps', []):
                        st.markdown(f"<span style='font-size:14px; color:#f87171;'>**{g['gap_id']}**: {g['description']}</span>", unsafe_allow_html=True)

        st.divider()
        st.markdown("### Coverage & Release Risk Prediction")
        if st.button("Generate Test Intelligence Report", type="primary"):
            with st.spinner("Analyzing historical run metadata..."):
                intel = api(f"/projects/{st.session_state.pid}/intelligence", "POST", {"include_llm_suggestions": True})
                if intel:
                    st.session_state.intel = intel
        
        if "intel" in st.session_state and st.session_state.intel:
            intel = st.session_state.intel
            ic1, ic2, ic3 = st.columns(3)
            with ic1:
                with st.container(border=True):
                    case_type_coverage = intel['coverage'].get('case_type_coverage', 0)
                    st.metric("Test Matrix Coverage", f"{case_type_coverage*100:.0f}%")
            with ic2:
                with st.container(border=True):
                    risk_band = intel['release_risk']['risk_band']
                    st.metric("AI Release Risk", f"{risk_band} ({intel['release_risk']['predicted_risk']})")
            with ic3:
                with st.container(border=True):
                    st.markdown("**Critical Regression Suggestions**")
                    for c in intel.get('recommended_regression_suite', [])[:3]:
                        st.markdown(f"<span style='font-size:13px; color:#94a3b8;'>- {c['prompt'][:50]}...</span>", unsafe_allow_html=True)

    with t_cert:
        st.markdown("### Production Readiness & Certification")
        cert_t_id = st.selectbox("Select Target Environment", options=[t["id"] for t in targets], format_func=lambda x: next(t["name"] for t in targets if t["id"] == x))
        if cert_t_id:
            cc1, cc2 = st.columns([1, 1], gap="large")
            with cc1:
                st.markdown("**Cryptographic Release Gates**")
                if st.button("Generate CI/CD Certificate for Latest Run", type="primary", use_container_width=True):
                    completed = [r for r in runs if r["target_id"] == cert_t_id and r["status"] == "completed"]
                    if completed: api(f"/targets/{cert_t_id}/certificates", "POST", {"run_id": completed[0]["id"]}); st.success("HMAC Certificate Issued successfully.")
                    else: st.error("No completed run found for this target to certify.")
                for c in (api(f"/targets/{cert_t_id}/certificates") or []):
                    c_color = "#10b981" if c["status"] == "CERTIFIED" else "#ef4444"
                    st.markdown(f"<div class='dashboard-card' style='padding: 16px; margin-top: 12px;'><b style='color:{c_color}; font-size:15px;'>{c['status']}</b> &nbsp;|&nbsp; <span style='color:#cbd5e1; font-weight:600;'>Score: {c['payload'].get('composite_score')}</span> &nbsp;|&nbsp; <span style='color:#cbd5e1; font-weight:600;'>Risk: {c['payload'].get('predicted_risk_band')}</span><br><code style='font-size:11px; color:#64748b; background:#020617; border: 1px solid #1e293b; display:block; margin-top:10px; padding:6px; border-radius:6px;'>Sig: {c['signature']}</code></div>", unsafe_allow_html=True)
            with cc2:
                st.markdown("**Live Telemetry Drift**")
                drift_data = api(f"/targets/{cert_t_id}/monitor")
                if drift_data and drift_data.get("drift"):
                    with st.container(border=True):
                        dc1, dc2 = st.columns(2)
                        dc1.metric("Samples Ingested", drift_data["drift"].get("samples", 0))
                        dc2.metric("Drift vs Baseline", drift_data["drift"].get("drift_vs_baseline", "—"))

    # 6. TRACE EXPLORER TAB
    with t_runs:
        col1, col2 = st.columns([4, 1])
        col1.markdown("### Execution Trace Explorer")
        if col2.button("🔄 Sync Live Status", use_container_width=True): st.rerun()
            
        proj_runs = [r for r in runs if r["project_id"] == st.session_state.pid]
        
        has_running = any(r["status"] == "running" for r in proj_runs)
        
        if not proj_runs: st.info("No executions found. Trigger a QA pipeline from the Targets tab.")
            
        for r in proj_runs:
            with st.container(border=True):
                rc1, rc2, rc3, rc4, rc5 = st.columns(5)
                is_running = r["status"] == "running"
                status_color = "#3b82f6" if r["status"] == "completed" else "#f59e0b" if is_running else "#ef4444"
                
                rc1.markdown(f"**Run `#{r['id'].split('-')[0]}`**<br><span style='color:{status_color}; font-size:14px; font-weight:800;'>{r['status'].upper()}</span>", unsafe_allow_html=True)
                gate = r.get("release_gate")
                gate_color = "#10b981" if gate == "PASS" else "#f59e0b" if gate == "WARN" else "#ef4444"
                rc2.markdown(f"**Gate Status**<br><span style='color:{gate_color}; font-size:18px; font-weight:800;'>{gate if gate else ('PENDING' if is_running else 'FAIL')}</span>", unsafe_allow_html=True)
                rc3.metric("Composite", f"{float(r.get('score', 0)):.1f}" if r.get("score") is not None else "—")
                rc4.metric("Pass Rate", f"{int(float(r.get('pass_rate', 0))*100)}%" if r.get("pass_rate") is not None else "—")
                rc5.metric("Risk Score", f"{float(r.get('risk_score', 0)):.1f}" if r.get("risk_score") is not None else "—")
                
                if is_running:
                    st.markdown("<p style='color:#f59e0b; font-size:13px; margin-top:10px; font-weight:600; padding:10px; background:#f59e0b10; border-radius:6px;'>⏳ This pipeline is currently executing...</p>", unsafe_allow_html=True)
                elif not is_running and r.get("score") is None:
                    st.markdown("<p style='color:#ef4444; font-size:13px; margin-top:10px; font-weight:600; padding:10px; background:#ef444410; border-radius:6px;'>❌ Execution dropped. Target timed out or connection was blocked.</p>", unsafe_allow_html=True)

                if r["status"] == "completed":
                    with st.expander("Inspect Evaluation Traces & Rationale"):
                        bc1, bc2, bc3 = st.columns(3)
                        if bc1.button("🔗 Traceability", key=f"tr_{r['id']}", use_container_width=True): show_traceability(r['id'])
                        if bc2.button("⚖️ Regression", key=f"rg_{r['id']}", use_container_width=True): show_regression(r['id'])
                        if bc3.button("🌐 Network Traces", key=f"nw_{r['id']}", use_container_width=True): show_traces(r['id'])
                        st.divider()

                        details = api(f"/runs/{r['id']}")
                        if details and "results" in details:
                            for res in details["results"]:
                                with st.container(border=True):
                                    st.markdown(f"#### `{res['case_type'].upper()} VECTOR` - {'✅ SECURE' if res['passed'] else '❌ VULNERABLE'}")
                                    if res.get('evidence', {}).get('hallucination_detected'): st.error("🚨 Critical AI Hallucination Detected during synthesis.")
                                    st.markdown("**Injected Prompt:**")
                                    st.info(res['prompt'])
                                    st.markdown("**Agent Output / Behavior:**")
                                    resp_text = res.get('response', '')
                                    if "Error" in resp_text or not resp_text: st.error(resp_text or "No response received.")
                                    else: st.code(resp_text, language="text")
                                    
                                    ec1, ec2 = st.columns(2)
                                    with ec1:
                                        st.markdown("**Evaluation Engine Rationale:**")
                                        for rat in res.get('rationale', []): st.markdown(f"<span style='color:#94a3b8; font-size:13px;'>• {rat}</span>", unsafe_allow_html=True)
                                    with ec2:
                                        st.markdown("**Network & Telemetry Evidence:**")
                                        st.markdown(f"<span style='color:#94a3b8; font-size:13px; font-weight:600;'>Latency: {res.get('evidence', {}).get('latency_ms', 0):.0f}ms<br>Compute Tokens: {sum(res.get('evidence', {}).get('tokens', {}).values())}</span>", unsafe_allow_html=True)
                                    
                                    if res.get('evidence', {}).get('policy_findings'):
                                        st.warning("⚠️ Governance & Compliance Violations Triggered")
                                        for f in res['evidence']['policy_findings']: st.markdown(f"<span style='color:#f87171; font-size:13px; font-weight:600;'>[{f['severity'].upper()}] {f['rule_name']}: {f['detail']}</span>", unsafe_allow_html=True)

        if has_running:
            time.sleep(3)
            st.rerun()

# --- APP ROUTING ---
if not st.session_state.access_token: auth_view()
else: main_dashboard()