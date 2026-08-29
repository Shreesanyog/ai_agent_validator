import ipaddress,socket
from urllib.parse import urlparse,urljoin
import httpx
from bs4 import BeautifulSoup
from playwright.async_api import async_playwright
from ..core.config import settings

async def guard_url(url):
 u=urlparse(url); host=u.hostname or ''
 if u.scheme not in {'http','https'}: raise ValueError('Only HTTP(S) targets are supported')
 for x in socket.getaddrinfo(host,u.port or (443 if u.scheme=='https' else 80)):
  ip=ipaddress.ip_address(x[4][0])
  if not settings().allow_private_targets and (ip.is_private or ip.is_loopback or ip.is_link_local): raise ValueError('Private/loopback targets are disabled')

async def discover(url,mode):
 await guard_url(url)
 if mode=='openapi': return await discover_openapi(url)
 if mode=='browser': return await discover_browser(url)
 return {'mode':mode,'ready':True,'notes':['Configure request mapping or import transcripts.']}

async def discover_openapi(url):
 candidates=[url,urljoin(url,'/openapi.json'),urljoin(url,'/swagger.json')]
 async with httpx.AsyncClient(timeout=20,follow_redirects=True) as c:
  for x in candidates:
   try:
    r=await c.get(x);d=r.json()
    if 'paths' in d:return {'mode':'openapi','ready':True,'spec_url':x,'operations':[{'path':p,'method':m,'summary':o.get('summary','')} for p,v in d['paths'].items() for m,o in v.items() if m.lower() in {'get','post','put','patch'}]}
   except Exception: pass
 return {'mode':'openapi','ready':False,'notes':['No OpenAPI document found. Switch to browser mode or provide mapping.']}

async def discover_browser(url):
 async with async_playwright() as p:
  # Added anti-bot stealth parameters to bypass Cloudflare/WAF checks
  b=await p.chromium.launch(
      headless=settings().browser_headless,
      args=["--disable-blink-features=AutomationControlled"]
  )
  context = await b.new_context(
      user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
      viewport={"width": 1280, "height": 800}
  )
  page=await context.new_page()
  await page.add_init_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
  
  errors=[];page.on('console',lambda m: errors.append(m.text) if m.type=='error' else None)
  await page.goto(url,wait_until='domcontentloaded',timeout=settings().browser_timeout_ms);await page.wait_for_timeout(1500)
  data=await page.evaluate("""() => { const vis=e=>!!(e.offsetWidth||e.offsetHeight||e.getClientRects().length); const pick=s=>[...document.querySelectorAll(s)].filter(vis).map(e=>({tag:e.tagName.toLowerCase(),type:e.type||'',placeholder:e.placeholder||'',aria:e.getAttribute('aria-label')||'',text:(e.innerText||'').trim().slice(0,120)})).slice(0,30); return {title:document.title,text:document.body.innerText.slice(0,5000),inputs:pick('textarea,input,[contenteditable=true]'),buttons:pick('button,[role=button],input[type=submit]'),iframes:pick('iframe')}; }""")
  await b.close(); likely=bool(data['inputs'] and data['buttons']); return {'mode':'browser','ready':likely,'page':data,'console_errors':errors[:10],'recommended':{'input_selector':'textarea, input[type=text], [contenteditable=true]','submit_selector':'button[type=submit], button','response_selector':'main, [role=log], [aria-live=polite]'},'notes':[] if likely else ['No obvious chat input and submit control found. Supply selectors or use transcript mode.']}