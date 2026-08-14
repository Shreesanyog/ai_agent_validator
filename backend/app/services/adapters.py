import asyncio,json,time
from playwright.async_api import async_playwright
from ..core.config import settings
from .discovery import guard_url

class BrowserAdapter:
 async def invoke(self,target,prompt):
  await guard_url(target.base_url)
  cfg=target.config or {}
  d=target.discovery or {}
  rec=d.get('recommended',{})
  inp=cfg.get('input_selector') or rec.get('input_selector')
  submit=cfg.get('submit_selector') or rec.get('submit_selector')
  response_sel=cfg.get('response_selector') or rec.get('response_selector')
  start=time.perf_counter()
  
  async with async_playwright() as p:
   # 1. ANTI-BOT EVASION: Mask the headless browser to look like a real Windows user
   b=await p.chromium.launch(
       headless=settings().browser_headless, 
       args=['--disable-blink-features=AutomationControlled']
   )
   ctx = await b.new_context(user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36')
   page = await ctx.new_page()
   errs=[]
   page.on('pageerror',lambda e:errs.append(str(e)))
   
   # 2. HEAVY DOM WAIT: Wait for the network to quiet down, not just the DOM to load
   await page.goto(target.base_url, wait_until='networkidle', timeout=settings().browser_timeout_ms)
   
   try: 
    box = page.locator(inp).first
    await box.wait_for(state="visible", timeout=15000)
   except Exception: 
    await b.close(); raise RuntimeError(f'Input {inp} not found. The site may be blocking bots or requires login.')
   
   before_text = await page.locator(response_sel).last.inner_text() if await page.locator(response_sel).count() else ''
   
   # 3. REACT STATE BYPASS: Click, clear, and type sequentially like a human
   await box.click()
   await page.wait_for_timeout(500)
   await box.evaluate('(el) => { if(el.value !== undefined) el.value = ""; else el.innerText = ""; }')
   await box.press_sequentially(prompt, delay=15) # Triggers React onChange events
   await page.wait_for_timeout(1500) # Give UI time to enable the submit button
   
   # 4. AGGRESSIVE SUBMIT: Try normal, then forced, then raw Javascript click
   if submit and await page.locator(submit).count():
    btn = page.locator(submit).last
    try:
     await btn.wait_for(state='visible', timeout=5000)
     await btn.click(force=True, timeout=3000) # Punch through transparent overlays
    except Exception:
     try: await btn.evaluate('b => b.click()') # Fallback to JS execution
     except Exception: await box.press('Enter') # Absolute fallback
   else: 
    await box.press('Enter')
   
   # 5. RESPONSE EXTRACTION: Wait for the last element in the response array to change
   try: 
    await page.wait_for_function(
     '(x)=>{const e=document.querySelectorAll(x.s); if(!e.length) return false; const last=e[e.length-1]; return last && last.innerText.trim() !== x.b.trim() && last.innerText.trim() !== "";}',
     arg={'s':response_sel,'b':before_text},
     timeout=60000, polling=1000
    )
   except Exception: 
    await page.wait_for_timeout(5000)
   
   # Safely extract the final text
   after_elems = page.locator(response_sel)
   if await after_elems.count(): after_text = await after_elems.last.inner_text()
   else: after_text = await page.locator('body').inner_text()
   
   await b.close()
   
   # Clean up string diffing
   text = after_text[len(before_text):].strip() if after_text.startswith(before_text) else after_text.strip()
   if not text: text = after_text.strip()
   
   return {'text':text[-8000:],'latency_ms':(time.perf_counter()-start)*1000,'evidence':{'adapter':'browser','url':target.base_url,'page_errors':errs[:10]}}

class TranscriptAdapter:
 async def invoke(self,target,prompt): raise RuntimeError('Transcript mode requires response upload; it cannot execute automatically.')

def adapter(target):
 if target.mode.value=='browser': return BrowserAdapter()
 return TranscriptAdapter()