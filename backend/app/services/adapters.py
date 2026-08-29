"""Target adapters: how AVaaS actually drives a system under test."""
import asyncio, json, time, uuid
from playwright.async_api import async_playwright
from ..core.config import settings
from ..core.security import decrypt
from .discovery import guard_url

COMMON_RESPONSE_KEYS = ('response', 'message', 'answer', 'output', 'text', 'reply', 'result', 'content')

def _auth_headers(target) -> dict:
    if not target.auth_encrypted:
        return {}
    try:
        raw = decrypt(target.auth_encrypted)
        auth = json.loads(raw) if raw.strip().startswith('{') else eval(raw, {'__builtins__': {}}, {})
    except Exception:
        return {}
    if not isinstance(auth, dict):
        return {}
    if auth.get('bearer'):
        return {'Authorization': f"Bearer {auth['bearer']}"}
    if auth.get('api_key'):
        return {auth.get('api_key_header', 'X-API-Key'): auth['api_key']}
    return {k: str(v) for k, v in auth.get('headers', {}).items()}

def _extract(payload, response_path: str | None):
    if response_path:
        cur = payload
        for part in response_path.split('.'):
            if isinstance(cur, list) and part.isdigit():
                cur = cur[int(part)]
            elif isinstance(cur, dict):
                cur = cur.get(part)
            else:
                return ''
            if cur is None:
                return ''
        return cur if isinstance(cur, str) else json.dumps(cur)
    if isinstance(payload, str):
        return payload
    if isinstance(payload, dict):
        for key in COMMON_RESPONSE_KEYS:
            if isinstance(payload.get(key), str):
                return payload[key]
    return json.dumps(payload)

class RestAdapter:
    async def invoke_case(self, target, case):
        import httpx
        await guard_url(target.base_url)
        cfg = target.config or {}
        method = (cfg.get('method') or 'POST').upper()
        path = cfg.get('path') or ''
        url = target.base_url.rstrip('/') + ('/' + path.lstrip('/') if path else '')
        prompt_field = cfg.get('prompt_field', 'message')
        response_path = cfg.get('response_path')
        session_field = cfg.get('session_field', 'session_id')
        headers = {'Content-Type': 'application/json', **_auth_headers(target), **(cfg.get('headers') or {})}

        turns = case.get('turns') or [case.get('prompt', '')]
        session_id = f"avaas-{int(time.time()*1000)}"
        transcript, tool_calls, statuses = [], [], []
        start = time.perf_counter()
        last_text = ''
        correlation_id = f"avaas-exec-{uuid.uuid4().hex[:12]}"
        s = settings()
        retries = cfg.get('max_retries', s.request_max_retries)
        backoff = cfg.get('backoff_seconds', s.request_backoff_seconds)
        rate = cfg.get('rate_limit_per_sec', s.request_rate_limit_per_sec)

        async def _send(client, method, url, body, headers):
            last_exc = None
            for attempt in range(retries + 1):
                try:
                    if method == 'GET':
                        resp = await client.get(url, params=body, headers=headers)
                    else:
                        resp = await client.request(method, url, json=body, headers=headers)
                    if resp.status_code == 429 or resp.status_code >= 500:
                        if attempt < retries:
                            await asyncio.sleep(backoff * (2 ** attempt))
                            continue
                    return resp
                except (httpx.TransportError, httpx.TimeoutException) as e:
                    last_exc = e
                    if attempt < retries:
                        await asyncio.sleep(backoff * (2 ** attempt))
                        continue
                    raise
            if last_exc:
                raise last_exc

        async with httpx.AsyncClient(timeout=cfg.get('timeout', 60), follow_redirects=True) as client:
            for turn in turns:
                body = dict(cfg.get('body_template') or {})
                body[prompt_field] = turn
                if session_field:
                    body[session_field] = session_id
                req_headers = {**headers, 'X-Request-ID': correlation_id}
                if rate and rate > 0:
                    await asyncio.sleep(1.0 / rate)
                r = await _send(client, method, url, body, req_headers)
                statuses.append(r.status_code)
                r.raise_for_status()
                try:
                    payload = r.json()
                except Exception:
                    payload = r.text
                last_text = _extract(payload, response_path)
                transcript.append({'user': turn, 'agent': last_text[:2000]})
                if isinstance(payload, dict):
                    for key in ('tool_calls', 'tools_used', 'steps', 'trace'):
                        if payload.get(key):
                            tool_calls.append({key: payload[key]})

        return {
            'text': last_text[-8000:],
            'latency_ms': (time.perf_counter() - start) * 1000,
            'evidence': {
                'adapter': 'rest', 'url': url, 'method': method,
                'turns': len(turns), 'transcript': transcript,
                'status_codes': statuses, 'tool_calls': tool_calls[:10],
                'session_id': session_id, 'correlation_id': correlation_id,
            },
        }

    async def invoke(self, target, prompt):
        return await self.invoke_case(target, {'prompt': prompt})

class BrowserAdapter:
    async def invoke_case(self, target, case):
        await guard_url(target.base_url)
        cfg = target.config or {}
        d = target.discovery or {}
        rec = d.get('recommended', {})
        inp = cfg.get('input_selector') or rec.get('input_selector')
        submit = cfg.get('submit_selector') or rec.get('submit_selector')
        response = cfg.get('response_selector') or rec.get('response_selector')
        turns = case.get('turns') or [case.get('prompt', '')]
        start = time.perf_counter()
        transcript = []
        last_text = ''

        async with async_playwright() as p:
            # Stealth and anti-bot launch params
            b = await p.chromium.launch(
                headless=settings().browser_headless,
                args=["--disable-blink-features=AutomationControlled"]
            )
            context = await b.new_context(
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                viewport={"width": 1280, "height": 800}
            )
            page = await context.new_page()
            await page.add_init_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
            
            errs = []
            page.on('pageerror', lambda e: errs.append(str(e)))
            await page.goto(target.base_url, wait_until='domcontentloaded', timeout=settings().browser_timeout_ms)

            try:
                await page.locator(inp).first.wait_for(state='visible', timeout=15000)
            except Exception:
                await b.close()
                raise RuntimeError(f'Input {inp} not found. Is the page still loading or blocking bots?')

            for turn in turns:
                before = await page.locator(response).last.inner_text() if await page.locator(response).count() else ''
                box = page.locator(inp).first
                
                # HUMAN TYPING FIX: Clears the box, then types bit by bit
                await box.fill('')
                await box.focus()
                await box.press_sequentially(turn, delay=65) 
                
                if submit and await page.locator(submit).count():
                    await page.locator(submit).last.click()
                else:
                    await box.press('Enter')
                
                try:
                    await page.wait_for_function(
                        '(x)=>{const e=document.querySelector(x.s);return e && e.innerText.trim()!==x.b.trim()}',
                        arg={'s': response, 'b': before}, timeout=45000)
                    # Give it a tiny bit extra to finish streaming
                    await page.wait_for_timeout(1000) 
                except Exception:
                    await page.wait_for_timeout(5000)
                
                after = await page.locator(response).last.inner_text() if await page.locator(response).count() else await page.locator('body').inner_text()
                last_text = after[len(before):].strip() if after.startswith(before) else after.strip()
                transcript.append({'user': turn, 'agent': last_text[:2000]})
            
            await b.close()

        return {
            'text': last_text[-8000:],
            'latency_ms': (time.perf_counter() - start) * 1000,
            'evidence': {'adapter': 'browser', 'url': target.base_url, 'page_errors': errs[:10],
                          'turns': len(turns), 'transcript': transcript},
        }

    async def invoke(self, target, prompt):
        return await self.invoke_case(target, {'prompt': prompt})

class TranscriptAdapter:
    async def invoke_case(self, target, case):
        raise RuntimeError('Transcript mode requires response upload; it cannot execute automatically.')

    async def invoke(self, target, prompt):
        return await self.invoke_case(target, {'prompt': prompt})

def adapter(target):
    mode = target.mode.value
    if mode == 'browser':
        return BrowserAdapter()
    if mode in ('rest', 'openapi'):
        return RestAdapter()
    return TranscriptAdapter()