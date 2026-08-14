import json,httpx
from google import genai
from ..core.config import settings

class LLM:
 async def json(self,system,prompt):
  s=settings(); errors=[]
  try:
   async with httpx.AsyncClient(timeout=s.ollama_timeout) as c:
    r=await c.post(s.ollama_base_url.rstrip('/')+'/api/generate',json={'model':s.ollama_model,'system':system,'prompt':prompt,'stream':False,'format':'json'});r.raise_for_status();d=r.json();txt=d['response']
    return json.loads(txt),'ollama',{'prompt':d.get('prompt_eval_count',0),'completion':d.get('eval_count',0)}
  except Exception as e: errors.append(type(e).__name__)
  if not s.gemini_api_key: raise RuntimeError('Ollama failed and Gemini is not configured: '+','.join(errors))
  
  client=genai.Client(api_key=s.gemini_api_key.get_secret_value());out=await client.aio.models.generate_content(model=s.gemini_model,contents=system+'\n\n'+prompt,config={'response_mime_type':'application/json'})
  u=out.usage_metadata;return json.loads(out.text or '{}'),'gemini',{'prompt':u.prompt_token_count if u else 0,'completion':u.candidates_token_count if u else 0}