import asyncio,json,time
from playwright.async_api import async_playwright
from ..core.config import settings
from .discovery import guard_url
class BrowserAdapter:
 async def invoke(self,target,prompt):
  await guard_url(target.base_url);cfg=target.config or {};d=target.discovery or {};rec=d.get('recommended',{}); inp=cfg.get('input_selector') or rec.get('input_selector');submit=cfg.get('submit_selector') or rec.get('submit_selector');response=cfg.get('response_selector') or rec.get('response_selector');start=time.perf_counter()
  async with async_playwright() as p:
   b=await p.chromium.launch(headless=settings().browser_headless);page=await b.new_page();errs=[];page.on('pageerror',lambda e:errs.append(str(e)));await page.goto(target.base_url,wait_until='domcontentloaded',timeout=settings().browser_timeout_ms);await page.wait_for_timeout(1000)
   before=await page.locator(response).last.inner_text() if await page.locator(response).count() else ''
   box=page.locator(inp).first
   if not await box.count(): raise RuntimeError('No input detected. Run discovery or configure input_selector.')
   await box.fill(prompt)
   if submit and await page.locator(submit).count(): await page.locator(submit).last.click()
   else: await box.press('Enter')
   try: await page.wait_for_function('(x)=>{const e=document.querySelector(x.s);return e && e.innerText.trim()!==x.b.trim()}',arg={'s':response,'b':before},timeout=settings().browser_timeout_ms)
   except Exception: await page.wait_for_timeout(3000)
   after=await page.locator(response).last.inner_text() if await page.locator(response).count() else await page.locator('body').inner_text();await b.close()
   text=after[len(before):].strip() if after.startswith(before) else after.strip();return {'text':text[-8000:],'latency_ms':(time.perf_counter()-start)*1000,'evidence':{'adapter':'browser','url':target.base_url,'page_errors':errs[:10]}}
class TranscriptAdapter:
 async def invoke(self,target,prompt): raise RuntimeError('Transcript mode requires response upload; it cannot execute automatically.')
def adapter(target):
 if target.mode.value=='browser': return BrowserAdapter()
 return TranscriptAdapter()
