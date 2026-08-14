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
r=APIRouter(prefix=settings().api_v1_prefix)
def audit(db,p,a,res,rid=None):db.add(Audit(tenant_id=p.tenant_id,user_id=p.user_id,action=a,resource=res,resource_id=rid))
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
