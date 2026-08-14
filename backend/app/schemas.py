from pydantic import BaseModel,EmailStr,Field,HttpUrl
from .models import TargetMode
class Register(BaseModel): organization:str=Field(min_length=2); slug:str=Field(pattern=r'^[a-z0-9-]+$'); email:EmailStr; password:str=Field(min_length=12)
class Login(BaseModel): tenant_slug:str; email:EmailStr; password:str
class Refresh(BaseModel): refresh_token:str
class ProjectIn(BaseModel): name:str; description:str=''
class TargetIn(BaseModel): name:str; base_url:HttpUrl; mode:TargetMode=TargetMode.browser; auth:dict|None=None; config:dict={}
class RequirementIn(BaseModel): text:str; acceptance:list[str]=[]; authoritative:bool=True
class RunIn(BaseModel): is_baseline:bool=False; baseline_id:str|None=None; optional_context:str=''; max_cases:int=Field(default=10,ge=1,le=30)
