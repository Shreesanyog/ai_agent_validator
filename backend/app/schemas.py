from pydantic import BaseModel,EmailStr,Field,HttpUrl
from .models import TargetMode,PolicyCategory,Severity
class Register(BaseModel): organization:str=Field(min_length=2); slug:str=Field(pattern=r'^[a-z0-9-]+$'); email:EmailStr; password:str=Field(min_length=12)
class Login(BaseModel): tenant_slug:str; email:EmailStr; password:str
class Refresh(BaseModel): refresh_token:str
class ProjectIn(BaseModel): name:str; description:str=''
class TargetIn(BaseModel): name:str; base_url:HttpUrl; mode:TargetMode=TargetMode.browser; auth:dict|None=None; config:dict={}
class RequirementIn(BaseModel): text:str; acceptance:list[str]=[]; authoritative:bool=True
class RunIn(BaseModel): is_baseline:bool=False; baseline_id:str|None=None; optional_context:str=''; max_cases:int=Field(default=10,ge=1,le=30)
class PolicyRuleIn(BaseModel): name:str; category:PolicyCategory; pattern:str=''; description:str=''; severity:Severity=Severity.medium
class PromptVersionIn(BaseModel): system_prompt:str=''; config_snapshot:dict={}; notes:str=''
class WorkflowIn(BaseModel): name:str; description:str=''; steps:list[str]=Field(min_length=1)
class WorkflowRunIn(BaseModel): max_cases:int=Field(default=6,ge=1,le=20); optional_context:str=''
class CertificateIn(BaseModel): run_id:str; prompt_version_id:str|None=None
class MonitorSampleIn(BaseModel): prompt:str; response:str; source:str='production'
class MonitorBatchIn(BaseModel): samples:list[MonitorSampleIn]=Field(min_length=1,max_length=200); baseline_run_id:str|None=None
class IntelligenceIn(BaseModel): run_id:str|None=None; include_llm_suggestions:bool=True
class AnalysisIn(BaseModel):
    use_case_definition: str = ''
    business_requirements: str = ''
    pdf_documents: str = ''
    agent_description: str = ''
    system_prompt: str = ''
    tools: list[str] = []
    tool_schemas: dict = {}
    documentation: str = ''
