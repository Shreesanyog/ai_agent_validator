from dataclasses import dataclass
from fastapi import Depends,HTTPException
from fastapi.security import HTTPBearer,HTTPAuthorizationCredentials
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from ..db import get_db
from ..models import Membership,Role
from ..core.security import decode_token
bearer=HTTPBearer()
@dataclass(frozen=True)
class Principal: user_id:str; tenant_id:str; role:Role
async def current(c:HTTPAuthorizationCredentials=Depends(bearer),db:AsyncSession=Depends(get_db)):
 try: p=decode_token(c.credentials); assert p.get('type')=='access'; role=Role(p['role'])
 except Exception: raise HTTPException(401,'Invalid or expired access token')
 m=(await db.execute(select(Membership).where(Membership.user_id==p['sub'],Membership.tenant_id==p['tid'],Membership.active.is_(True)))).scalar_one_or_none()
 if not m: raise HTTPException(403,'Membership inactive')
 return Principal(p['sub'],p['tid'],role)
def allow(*roles):
 async def dep(p:Principal=Depends(current)):
  if p.role not in roles: raise HTTPException(403,'Insufficient permission')
  return p
 return dep
