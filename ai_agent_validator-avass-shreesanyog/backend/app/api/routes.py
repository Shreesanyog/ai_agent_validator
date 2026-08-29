import re
from datetime import datetime,timedelta,timezone
from fastapi import APIRouter,Depends,HTTPException,BackgroundTasks
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from ..db import get_db
from ..models import *
from ..schemas import *
from ..core.config import settings
from ..core.security import *
from .deps import Principal,current,allow
from ..services.discovery import discover
from ..services.pipeline import execute_run
from ..services.workflow import execute_workflow
from ..services.kpi import tenant_kpis
from ..services import test_intelligence as ti
from ..services import certification, monitoring, regression
from ..services.llm import LLM
from ..services.analysis import analyze
r=APIRouter(prefix=settings().api_v1_prefix)
def audit(db,p,a,res,rid=None,md=None):db.add(Audit(tenant_id=p.tenant_id,user_id=p.user_id,action=a,resource=res,resource_id=rid,metadata_json=md or {}))
async def issue(db,u,m):
 raw=new_refresh();db.add(RefreshToken(user_id=u.id,tenant_id=m.tenant_id,token_hash=token_hash(raw),expires_at=datetime.now(timezone.utc)+timedelta(days=settings().refresh_token_days)));await db.commit();return {'access_token':access_token(u.id,m.tenant_id,m.role.value),'refresh_token':raw,'tenant_id':m.tenant_id,'role':m.role}
@r.post('/auth/register')
async def register(x:Register,db:AsyncSession=Depends(get_db)):
 if not settings().allow_public_registration:raise HTTPException(403,'Registration disabled')
 if (await db.execute(select(User).where(User.email==x.email))).scalar_one_or_none():raise HTTPException(409,'Email exists')
 if (await db.execute(select(Tenant).where(Tenant.slug==x.slug))).scalar_one_or_none():raise HTTPException(409,'Slug exists')
 u=User(email=x.email,password_hash=hash_password(x.password));t=Tenant(name=x.organization,slug=x.slug);db.add_all([u,t]);await db.flush();m=Membership(user_id=u.id,tenant_id=t.id,role=Role.owner);db.add(m);return await issue(db,u,m)
@r.post('/auth/login')
async def login(x:Login,db:AsyncSession=Depends(get_db)):
 u=(await db.execute(select(User).where(User.email==x.email,User.active.is_(True)))).scalar_one_or_none();t=(await db.execute(select(Tenant).where(Tenant.slug==x.tenant_slug,Tenant.active.is_(True)))).scalar_one_or_none()
 if not u or not t or not verify_password(x.password,u.password_hash):raise HTTPException(401,'Invalid credentials')
 m=(await db.execute(select(Membership).where(Membership.user_id==u.id,Membership.tenant_id==t.id,Membership.active.is_(True)))).scalar_one_or_none()
 if not m:raise HTTPException(403,'No active membership')
 return await issue(db,u,m)
@r.post('/auth/refresh')
async def refresh(x:Refresh,db:AsyncSession=Depends(get_db)):
 rt=(await db.execute(select(RefreshToken).where(RefreshToken.token_hash==token_hash(x.refresh_token),RefreshToken.revoked.is_(False)))).scalar_one_or_none()
 if not rt or rt.expires_at.replace(tzinfo=timezone.utc)<datetime.now(timezone.utc):raise HTTPException(401,'Refresh token invalid')
 rt.revoked=True;u=(await db.execute(select(User).where(User.id==rt.user_id))).scalar_one();m=(await db.execute(select(Membership).where(Membership.user_id==u.id,Membership.tenant_id==rt.tenant_id))).scalar_one();return await issue(db,u,m)
@r.get('/me')
async def me(p:Principal=Depends(current)):return p
@r.get('/projects')
async def projects(p=Depends(current),db=Depends(get_db)):return list((await db.execute(select(Project).where(Project.tenant_id==p.tenant_id))).scalars())
@r.post('/projects')
async def project(x:ProjectIn,p=Depends(allow(Role.owner,Role.admin,Role.qa)),db=Depends(get_db)):
 o=Project(tenant_id=p.tenant_id,created_by=p.user_id,**x.model_dump());db.add(o);await db.flush();audit(db,p,'create','project',o.id);await db.commit();return o
@r.get('/projects/{pid}/targets')
async def targets(pid:str,p=Depends(current),db=Depends(get_db)):return list((await db.execute(select(Target).where(Target.project_id==pid,Target.tenant_id==p.tenant_id))).scalars())
@r.post('/projects/{pid}/targets')
async def target(pid:str,x:TargetIn,p=Depends(allow(Role.owner,Role.admin,Role.qa)),db=Depends(get_db)):
 if not (await db.execute(select(Project).where(Project.id==pid,Project.tenant_id==p.tenant_id))).scalar_one_or_none():raise HTTPException(404)
 o=Target(tenant_id=p.tenant_id,project_id=pid,created_by=p.user_id,name=x.name,base_url=str(x.base_url),mode=x.mode,auth_encrypted=encrypt(str(x.auth)) if x.auth else None,config=x.config);db.add(o);await db.flush();audit(db,p,'create','target',o.id);await db.commit();return o
@r.post('/targets/{tid}/discover')
async def discovery(tid:str,p=Depends(allow(Role.owner,Role.admin,Role.qa)),db=Depends(get_db)):
 o=(await db.execute(select(Target).where(Target.id==tid,Target.tenant_id==p.tenant_id))).scalar_one_or_none()
 if not o:raise HTTPException(404)
 try:o.discovery=await discover(o.base_url,o.mode.value)
 except Exception as e:raise HTTPException(422,str(e))
 await db.commit();return o.discovery
@r.post('/projects/{pid}/requirements')
async def req(pid:str,x:RequirementIn,p=Depends(allow(Role.owner,Role.admin,Role.qa)),db=Depends(get_db)):
 o=Requirement(tenant_id=p.tenant_id,project_id=pid,source='user',**x.model_dump());db.add(o);await db.commit();return o
@r.get('/runs')
async def runs(p=Depends(current),db=Depends(get_db)):return list((await db.execute(select(Run).where(Run.tenant_id==p.tenant_id).order_by(Run.created_at.desc()))).scalars())
@r.post('/targets/{tid}/runs')
async def start(tid:str,x:RunIn,tasks:BackgroundTasks,p=Depends(allow(Role.owner,Role.admin,Role.qa)),db=Depends(get_db)):
 target=(await db.execute(select(Target).where(Target.id==tid,Target.tenant_id==p.tenant_id))).scalar_one_or_none()
 if not target:raise HTTPException(404)
 o=Run(tenant_id=p.tenant_id,project_id=target.project_id,target_id=tid,created_by=p.user_id,is_baseline=x.is_baseline,baseline_id=x.baseline_id);db.add(o);await db.flush();audit(db,p,'start','run',o.id);await db.commit();tasks.add_task(execute_run,o.id,p.tenant_id,x.max_cases,x.optional_context);return o
@r.get('/runs/{rid}')
async def detail(rid:str,p=Depends(current),db=Depends(get_db)):
 o=(await db.execute(select(Run).where(Run.id==rid,Run.tenant_id==p.tenant_id))).scalar_one_or_none()
 if not o:raise HTTPException(404)
 xs=list((await db.execute(select(Result).where(Result.run_id==rid,Result.tenant_id==p.tenant_id))).scalars());return {'run':o,'results':xs}
@r.get('/runs/{rid}/findings')
async def run_findings(rid:str,p=Depends(current),db=Depends(get_db)):
 return list((await db.execute(select(PolicyFinding).where(PolicyFinding.run_id==rid,PolicyFinding.tenant_id==p.tenant_id))).scalars())

# --- Governance: Policy / Compliance / PII / Security / Responsible-AI rules ---
@r.get('/projects/{pid}/policies')
async def policies(pid:str,p=Depends(current),db=Depends(get_db)):return list((await db.execute(select(PolicyRule).where(PolicyRule.project_id==pid,PolicyRule.tenant_id==p.tenant_id))).scalars())
@r.post('/projects/{pid}/policies')
async def policy(pid:str,x:PolicyRuleIn,p=Depends(allow(Role.owner,Role.admin,Role.qa)),db=Depends(get_db)):
 o=PolicyRule(tenant_id=p.tenant_id,project_id=pid,**x.model_dump());db.add(o);await db.flush();audit(db,p,'create','policy_rule',o.id);await db.commit();return o
@r.delete('/policies/{polid}')
async def delete_policy(polid:str,p=Depends(allow(Role.owner,Role.admin)),db=Depends(get_db)):
 o=(await db.execute(select(PolicyRule).where(PolicyRule.id==polid,PolicyRule.tenant_id==p.tenant_id))).scalar_one_or_none()
 if not o:raise HTTPException(404)
 o.active=False;audit(db,p,'deactivate','policy_rule',o.id);await db.commit();return {'ok':True}

# --- Governance: Prompt / config version history for a target ---
@r.get('/targets/{tid}/prompt-versions')
async def prompt_versions(tid:str,p=Depends(current),db=Depends(get_db)):return list((await db.execute(select(PromptVersion).where(PromptVersion.target_id==tid,PromptVersion.tenant_id==p.tenant_id).order_by(PromptVersion.version_no.desc()))).scalars())
@r.post('/targets/{tid}/prompt-versions')
async def prompt_version(tid:str,x:PromptVersionIn,p=Depends(allow(Role.owner,Role.admin,Role.qa)),db=Depends(get_db)):
 last=(await db.execute(select(PromptVersion).where(PromptVersion.target_id==tid,PromptVersion.tenant_id==p.tenant_id).order_by(PromptVersion.version_no.desc()))).scalars().first()
 o=PromptVersion(tenant_id=p.tenant_id,target_id=tid,version_no=(last.version_no+1 if last else 1),created_by=p.user_id,**x.model_dump());db.add(o);await db.flush();audit(db,p,'create','prompt_version',o.id);await db.commit();return o

# --- Multi-agent / end-to-end workflow validation ---
@r.get('/projects/{pid}/workflows')
async def workflows(pid:str,p=Depends(current),db=Depends(get_db)):return list((await db.execute(select(Workflow).where(Workflow.project_id==pid,Workflow.tenant_id==p.tenant_id))).scalars())
@r.post('/projects/{pid}/workflows')
async def workflow(pid:str,x:WorkflowIn,p=Depends(allow(Role.owner,Role.admin,Role.qa)),db=Depends(get_db)):
 o=Workflow(tenant_id=p.tenant_id,project_id=pid,created_by=p.user_id,**x.model_dump());db.add(o);await db.flush();audit(db,p,'create','workflow',o.id);await db.commit();return o
@r.post('/workflows/{wid}/runs')
async def start_workflow(wid:str,x:WorkflowRunIn,tasks:BackgroundTasks,p=Depends(allow(Role.owner,Role.admin,Role.qa)),db=Depends(get_db)):
 wf=(await db.execute(select(Workflow).where(Workflow.id==wid,Workflow.tenant_id==p.tenant_id))).scalar_one_or_none()
 if not wf:raise HTTPException(404)
 o=WorkflowRun(tenant_id=p.tenant_id,workflow_id=wid,created_by=p.user_id);db.add(o);await db.flush();audit(db,p,'start','workflow_run',o.id);await db.commit();tasks.add_task(execute_workflow,o.id,p.tenant_id,x.max_cases,x.optional_context);return o
@r.get('/workflows/{wid}/runs')
async def workflow_runs(wid:str,p=Depends(current),db=Depends(get_db)):return list((await db.execute(select(WorkflowRun).where(WorkflowRun.workflow_id==wid,WorkflowRun.tenant_id==p.tenant_id).order_by(WorkflowRun.created_at.desc()))).scalars())
@r.get('/workflow-runs/{wrid}')
async def workflow_run_detail(wrid:str,p=Depends(current),db=Depends(get_db)):
 o=(await db.execute(select(WorkflowRun).where(WorkflowRun.id==wrid,WorkflowRun.tenant_id==p.tenant_id))).scalar_one_or_none()
 if not o:raise HTTPException(404)
 steps=list((await db.execute(select(Run).where(Run.id.in_(o.run_ids or ['__none__'])))).scalars());return {'workflow_run':o,'steps':steps}

# --- AgentOps portfolio KPI dashboard ---
@r.get('/kpis')
async def kpis(p=Depends(current),db=Depends(get_db)):
 rs=list((await db.execute(select(Run).where(Run.tenant_id==p.tenant_id))).scalars());return tenant_kpis(rs)

# ============================================================================
# AI Test Intelligence — coverage gaps, regression suites, release-risk prediction
# ============================================================================
@r.post('/projects/{pid}/intelligence')
async def intelligence(pid:str,x:IntelligenceIn,p=Depends(current),db=Depends(get_db)):
 """Mine run history for uncovered scenarios, a recommended regression suite, and a release-risk prediction."""
 runs=list((await db.execute(select(Run).where(Run.project_id==pid,Run.tenant_id==p.tenant_id).order_by(Run.created_at.desc()))).scalars())
 if not runs:raise HTTPException(404,'No runs for this project yet')
 reqs=list((await db.execute(select(Requirement).where(Requirement.project_id==pid,Requirement.tenant_id==p.tenant_id))).scalars())
 all_results=list((await db.execute(select(Result).where(Result.run_id.in_([q.id for q in runs]),Result.tenant_id==p.tenant_id))).scalars())
 candidate=next((q for q in runs if q.id==x.run_id),runs[0])
 cand_results=[q for q in all_results if q.run_id==candidate.id]
 by_run={}
 for q in all_results: by_run.setdefault(q.run_id,[]).append(q)
 cov=ti.coverage_gaps(cand_results,reqs)
 out={'candidate_run_id':candidate.id,'coverage':cov,
      'recommended_regression_suite':ti.recommend_regression_suite(by_run),
      'release_risk':ti.predict_release_risk(candidate,runs,cov)}
 if x.include_llm_suggestions:
  out['suggested_uncovered_scenarios']=await ti.suggest_uncovered_scenarios(LLM(),reqs,cand_results)
 audit(db,p,'analyze','intelligence',pid);await db.commit();return out

# ============================================================================
# Agent Certification — signed, verifiable release artifacts for CI/CD gates
# ============================================================================
@r.post('/targets/{tid}/certificates')
async def issue_certificate(tid:str,x:CertificateIn,p=Depends(allow(Role.owner,Role.admin)),db=Depends(get_db)):
 target=(await db.execute(select(Target).where(Target.id==tid,Target.tenant_id==p.tenant_id))).scalar_one_or_none()
 if not target:raise HTTPException(404,'Target not found')
 run=(await db.execute(select(Run).where(Run.id==x.run_id,Run.tenant_id==p.tenant_id))).scalar_one_or_none()
 if not run or run.status!=RunStatus.completed:raise HTTPException(422,'Certification requires a completed run')
 pv=(await db.execute(select(PromptVersion).where(PromptVersion.id==x.prompt_version_id,PromptVersion.tenant_id==p.tenant_id))).scalar_one_or_none() if x.prompt_version_id else None
 results=list((await db.execute(select(Result).where(Result.run_id==run.id,Result.tenant_id==p.tenant_id))).scalars())
 reqs=list((await db.execute(select(Requirement).where(Requirement.project_id==run.project_id,Requirement.tenant_id==p.tenant_id))).scalars())
 history=list((await db.execute(select(Run).where(Run.project_id==run.project_id,Run.tenant_id==p.tenant_id))).scalars())
 cov=ti.coverage_gaps(results,reqs);risk=ti.predict_release_risk(run,history,cov)
 cert=certification.build_certificate(run,target,pv,cov,risk)
 o=Certificate(tenant_id=p.tenant_id,target_id=tid,run_id=run.id,prompt_version_id=getattr(pv,'id',None),status=cert['payload']['status'],payload=cert['payload'],signature=cert['signature'],issued_by=p.user_id)
 db.add(o);await db.flush();audit(db,p,'issue','certificate',o.id);await db.commit();return o
@r.get('/targets/{tid}/certificates')
async def certificates(tid:str,p=Depends(current),db=Depends(get_db)):return list((await db.execute(select(Certificate).where(Certificate.target_id==tid,Certificate.tenant_id==p.tenant_id).order_by(Certificate.created_at.desc()))).scalars())
@r.get('/certificates/{cid}/verify')
async def verify_certificate(cid:str,p=Depends(current),db=Depends(get_db)):
 o=(await db.execute(select(Certificate).where(Certificate.id==cid,Certificate.tenant_id==p.tenant_id))).scalar_one_or_none()
 if not o:raise HTTPException(404)
 return {'certificate_id':o.id,**certification.verify({'payload':o.payload,'signature':o.signature})}

# ============================================================================
# Production Monitoring & Continuous Validation
# ============================================================================
@r.post('/targets/{tid}/monitor')
async def ingest_samples(tid:str,x:MonitorBatchIn,p=Depends(allow(Role.owner,Role.admin,Role.qa)),db=Depends(get_db)):
 """Ingest live interactions and score them through the same deterministic tiers used at release time."""
 target=(await db.execute(select(Target).where(Target.id==tid,Target.tenant_id==p.tenant_id))).scalar_one_or_none()
 if not target:raise HTTPException(404,'Target not found')
 pols=list((await db.execute(select(PolicyRule).where(PolicyRule.project_id==target.project_id,PolicyRule.tenant_id==p.tenant_id,PolicyRule.active.is_(True)))).scalars())
 stored=[]
 for smp in x.samples:
  sc=monitoring.score_sample(smp.prompt,smp.response,pols)
  o=MonitorSample(tenant_id=p.tenant_id,target_id=tid,prompt=smp.prompt,response=smp.response,rule_score=sc['rule_score'],policy_findings=sc['policy_findings'],passed=sc['passed'],source=smp.source)
  db.add(o);stored.append(o)
 await db.flush();audit(db,p,'ingest','monitor_samples',tid,);await db.commit()
 baseline=(await db.execute(select(Run).where(Run.id==x.baseline_run_id,Run.tenant_id==p.tenant_id))).scalar_one_or_none() if x.baseline_run_id else None
 return {'ingested':len(stored),'drift':monitoring.drift_report(stored,baseline)}
@r.get('/targets/{tid}/monitor')
async def monitor_report(tid:str,baseline_run_id:str|None=None,p=Depends(current),db=Depends(get_db)):
 samples=list((await db.execute(select(MonitorSample).where(MonitorSample.target_id==tid,MonitorSample.tenant_id==p.tenant_id).order_by(MonitorSample.created_at.desc()))).scalars())
 baseline=(await db.execute(select(Run).where(Run.id==baseline_run_id,Run.tenant_id==p.tenant_id))).scalar_one_or_none() if baseline_run_id else None
 return {'drift':monitoring.drift_report(samples,baseline),'recent_samples':samples[:50]}

# ============================================================================
# Compliance Reporting — auditable export for GRC stakeholders
# ============================================================================
@r.get('/projects/{pid}/compliance-report')
async def compliance_report(pid:str,p=Depends(current),db=Depends(get_db)):
 """Single auditable export: gates, governance findings by category/severity, certificates, and audit trail."""
 runs=list((await db.execute(select(Run).where(Run.project_id==pid,Run.tenant_id==p.tenant_id))).scalars())
 rids=[q.id for q in runs] or ['__none__']
 findings=list((await db.execute(select(PolicyFinding).where(PolicyFinding.run_id.in_(rids),PolicyFinding.tenant_id==p.tenant_id))).scalars())
 certs=list((await db.execute(select(Certificate).where(Certificate.run_id.in_(rids),Certificate.tenant_id==p.tenant_id))).scalars())
 audits=list((await db.execute(select(Audit).where(Audit.tenant_id==p.tenant_id).order_by(Audit.created_at.desc()).limit(200))).scalars())
 by_cat={};by_sev={}
 for f in findings:
  by_cat[f.category.value]=by_cat.get(f.category.value,0)+1
  by_sev[f.severity.value]=by_sev.get(f.severity.value,0)+1
 return {'project_id':pid,'generated_at':datetime.now(timezone.utc).isoformat(),
         'runs':{'total':len(runs),'passed':sum(1 for q in runs if q.release_gate=='PASS'),'warned':sum(1 for q in runs if q.release_gate=='WARN'),'failed':sum(1 for q in runs if q.release_gate=='FAIL')},
         'governance_findings':{'total':len(findings),'by_category':by_cat,'by_severity':by_sev},
         'certificates':[{'id':c.id,'status':c.status,'run_id':c.run_id,'issued_at':c.created_at.isoformat() if c.created_at else None} for c in certs],
         'audit_trail':[{'action':a.action,'resource':a.resource,'resource_id':a.resource_id,'at':a.created_at.isoformat() if a.created_at else None,'metadata':a.metadata_json} for a in audits]}

# ============================================================================
# Requirement & Use Case Analysis Engine
# ============================================================================
@r.post('/projects/{pid}/analysis')
async def run_analysis(pid:str,x:AnalysisIn,p=Depends(allow(Role.owner,Role.admin,Role.qa)),db=Depends(get_db)):
 """Convert unstructured inputs into structured, source-classified, traceable requirements."""
 if not (await db.execute(select(Project).where(Project.id==pid,Project.tenant_id==p.tenant_id))).scalar_one_or_none():raise HTTPException(404)
 last=(await db.execute(select(RequirementAnalysis).where(RequirementAnalysis.project_id==pid,RequirementAnalysis.tenant_id==p.tenant_id).order_by(RequirementAnalysis.version_no.desc()))).scalars().first()
 result,provider,tokens=await analyze(LLM(),**x.model_dump())
 o=RequirementAnalysis(tenant_id=p.tenant_id,project_id=pid,version_no=(last.version_no+1 if last else 1),inputs=x.model_dump(),analysis=result,llm_provider=provider,created_by=p.user_id)
 db.add(o);await db.flush();audit(db,p,'create','requirement_analysis',o.id,md={'tokens':tokens});await db.commit();return o
@r.get('/projects/{pid}/analysis')
async def analyses(pid:str,p=Depends(current),db=Depends(get_db)):return list((await db.execute(select(RequirementAnalysis).where(RequirementAnalysis.project_id==pid,RequirementAnalysis.tenant_id==p.tenant_id).order_by(RequirementAnalysis.version_no.desc()))).scalars())
@r.get('/projects/{pid}/analysis/latest')
async def latest_analysis(pid:str,p=Depends(current),db=Depends(get_db)):
 o=(await db.execute(select(RequirementAnalysis).where(RequirementAnalysis.project_id==pid,RequirementAnalysis.tenant_id==p.tenant_id).order_by(RequirementAnalysis.version_no.desc()))).scalars().first()
 if not o:raise HTTPException(404,'No analysis run yet for this project')
 return o

# ============================================================================
# Traceability — walk Use Case -> Requirement -> Test Scenario -> Execution -> Evaluation
# ============================================================================
@r.get('/runs/{rid}/traceability')
async def run_traceability(rid:str,p=Depends(current),db=Depends(get_db)):
 """Requirement/use-case coverage for one run, resolved against the latest structured analysis."""
 run=(await db.execute(select(Run).where(Run.id==rid,Run.tenant_id==p.tenant_id))).scalar_one_or_none()
 if not run:raise HTTPException(404)
 results=list((await db.execute(select(Result).where(Result.run_id==rid,Result.tenant_id==p.tenant_id))).scalars())
 an=(await db.execute(select(RequirementAnalysis).where(RequirementAnalysis.project_id==run.project_id,RequirementAnalysis.tenant_id==p.tenant_id).order_by(RequirementAnalysis.version_no.desc()))).scalars().first()
 req_index={req['requirement_id']:req for req in (an.analysis.get('requirements',[]) if an and an.analysis else [])}
 uc_index={uc['use_case_id']:uc for uc in (an.analysis.get('use_cases',[]) if an and an.analysis else [])}
 by_req={}
 for res in results:
  if not res.requirement_id:continue
  bucket=by_req.setdefault(res.requirement_id,{'requirement':req_index.get(res.requirement_id,{}).get('requirement'),
   'source':req_index.get(res.requirement_id,{}).get('source'),'results':[]})
  bucket['results'].append({'result_id':res.id,'case_type':res.case_type,'passed':res.passed,'composite_score':res.composite_score,'use_case_id':res.use_case_id,'scenario_id':res.scenario_id})
 return {'run_id':rid,'analysis_version':getattr(an,'version_no',None),'requirements_traced':len(by_req),
         'untraced_result_count':sum(1 for res in results if not res.requirement_id),
         'coverage_by_requirement':by_req,'use_cases':uc_index}

# ============================================================================
# Phase 4 — Baseline vs candidate regression + PASS/FAIL/BLOCKED release gate
# ============================================================================
@r.get('/runs/{rid}/regression')
async def run_regression(rid:str,baseline_id:str|None=None,p=Depends(current),db=Depends(get_db)):
 """Compare a candidate run against a baseline and return a release-gate decision."""
 cand=(await db.execute(select(Run).where(Run.id==rid,Run.tenant_id==p.tenant_id))).scalar_one_or_none()
 if not cand:raise HTTPException(404)
 bid=baseline_id or cand.baseline_id
 baseline=(await db.execute(select(Run).where(Run.id==bid,Run.tenant_id==p.tenant_id))).scalar_one_or_none() if bid else None
 if not baseline:
  # fall back to the most recent prior baseline run for this project
  baseline=(await db.execute(select(Run).where(Run.project_id==cand.project_id,Run.tenant_id==p.tenant_id,Run.is_baseline.is_(True),Run.id!=rid).order_by(Run.created_at.desc()))).scalars().first()
 results=list((await db.execute(select(Result).where(Result.run_id==rid,Result.tenant_id==p.tenant_id))).scalars())
 return regression.compare(cand,baseline,results)
