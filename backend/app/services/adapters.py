"""Target adapters: how AVaaS drives systems under test across REST, Browser, and Transcripts."""
import asyncio
import json
import re
import time
import uuid
from playwright.async_api import async_playwright
from ..core.config import settings
from ..core.security import decrypt
from .discovery import guard_url

COMMON_RESPONSE_KEYS = ('response', 'message', 'answer', 'output', 'text', 'reply', 'result', 'content')

ERROR_TERMINAL_PATTERNS = [
    "404 not found",
    "traceback (most recent call last)",
    "stexception",
    "search failed",
    "too many requests",
    "rate limit",
    "internal server error",
    "axioserror",
    "connection refused",
    "exception in thread",
    "error occurred"
]

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

        async with httpx.AsyncClient(timeout=cfg.get('timeout', 180), follow_redirects=True) as client:
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
                transcript.append({'user': turn, 'agent': last_text[:4000]})
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

async def _bypass_turnstile_if_present(page):
    try:
        await page.wait_for_timeout(1500)
        for frame in page.frames:
            if any(k in frame.url for k in ["cloudflare", "turnstile", "challenge"]):
                checkbox = frame.locator("input[type='checkbox'], .cb-i, #challenge-stage")
                if await checkbox.count():
                    await checkbox.first.click(delay=120)
                    await page.wait_for_timeout(2500)
                    return True
        cf = page.locator("css=div.cf-turnstile-wrapper >> css=input[type='checkbox'], css=#cf-stage, css=input[value='Verify you are human']")
        if await cf.count():
            await cf.first.click(delay=120)
            await page.wait_for_timeout(2500)
            return True
    except Exception:
        pass
    return False

# Comprehensive Selector Hierarchy (Works for both Nexus and Streamlit apps)
CANDIDATE_INPUT_SELECTORS = [
    "textarea[data-testid='stChatInputTextArea']",
    "div[data-testid='stChatInput'] textarea",
    "div[data-testid='stTextInput'] input",
    "input[placeholder*='Enter target topic' i]",
    "input[placeholder*='topic' i]",
    "input[placeholder*='Analyze' i]",
    "input[placeholder*='Ask' i]",
    "input[placeholder*='Search' i]",
    "input[placeholder*='query' i]",
    "input[placeholder*='prompt' i]",
    "input[type='text']",
    "textarea",
    "[contenteditable='true']"
]

CANDIDATE_SUBMIT_SELECTORS = [
    "button:has-text('Execute')",
    "button:has-text('Analyze')",
    "button:has-text('Submit')",
    "button:has-text('Send')",
    "button:has-text('Search')",
    "button[kind='primary']",
    "div[data-testid='stButton'] button",
    "button[type='submit']",
    "button"
]

async def resolve_locator(page, custom_sel, candidates, custom_iframe=None):
    """Deep inspection engine: Searches main page, then pierces iframes."""
    roots = [page]
    if custom_iframe:
        roots = [page.frame_locator(custom_iframe).first]
    else:
        roots = [page, page.frame_locator("iframe").first, page.frame_locator("iframe").last]

    sels = [custom_sel] if custom_sel else candidates

    for root in roots:
        for sel in sels:
            try:
                loc = root.locator(sel)
                count = await loc.count()
                for i in range(count):
                    el = loc.nth(i)
                    if await el.is_visible() and not await el.is_disabled():
                        return el, root
            except Exception:
                continue
    return None, None

class BrowserAdapter:
    async def invoke_case(self, target, case):
        await guard_url(target.base_url)
        cfg = target.config or {}
        custom_iframe = cfg.get('iframe_selector')
        custom_inp = cfg.get('input_selector')
        custom_submit = cfg.get('submit_selector')
        custom_resp = cfg.get('response_selector')
        
        turns = case.get('turns') or [case.get('prompt', '')]
        start = time.perf_counter()
        transcript = []
        last_text = ''
        global_timeout = cfg.get('timeout', 180000)

        async with async_playwright() as p:
            b = await p.chromium.launch(
                headless=settings().browser_headless,
                args=["--disable-blink-features=AutomationControlled", "--no-sandbox"]
            )
            context = await b.new_context(
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
                viewport={"width": 1366, "height": 768}
            )
            context.set_default_timeout(global_timeout)
            page = await context.new_page()
            await page.add_init_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
            
            errs = []
            page.on('pageerror', lambda e: errs.append(str(e)))
            
            await page.goto(target.base_url, wait_until='domcontentloaded', timeout=45000)
            await _bypass_turnstile_if_present(page)
            await page.wait_for_timeout(3500)

            for turn in turns:
                poll_start = time.time()
                active_input = None
                active_root = None
                
                # Dynamic re-binding per turn (Up to 30 seconds wait for Streamlit Cold-Starts)
                while time.time() - poll_start < 30:
                    active_input, active_root = await resolve_locator(page, custom_inp, CANDIDATE_INPUT_SELECTORS, custom_iframe)
                    if not active_input:
                        try:
                            loc = page.get_by_role("textbox")
                            for i in range(await loc.count()):
                                el = loc.nth(i)
                                if await el.is_visible() and not await el.is_disabled():
                                    active_input, active_root = el, page
                                    break
                        except Exception:
                            pass
                    
                    if active_input:
                        break
                    await page.wait_for_timeout(2000)

                if not active_input:
                    await b.close()
                    raise RuntimeError("Interactive input field not found. The target system may be unresponsive or asleep.")

                active_submit, _ = await resolve_locator(page, custom_submit, CANDIDATE_SUBMIT_SELECTORS, custom_iframe)
                if not active_submit:
                    try:
                        s_loc = active_root.get_by_role("button", name=re.compile(r"execute|analyze|submit|send|search|chat", re.I))
                        for i in range(await s_loc.count()):
                            if await s_loc.nth(i).is_visible() and not await s_loc.nth(i).is_disabled():
                                active_submit = s_loc.nth(i)
                                break
                    except Exception:
                        pass

                before_text = await active_root.locator('body').inner_text()
                
                await active_input.fill('')
                await active_input.focus()
                await active_input.press_sequentially(turn, delay=35)

                if active_submit and await active_submit.is_visible():
                    await active_submit.click()
                else:
                    await active_input.press('Enter')

                # --- EXACT RESTORATION OF YOUR OLD WORKING LOGIC ---
                poll_start = time.time()
                current_text = ""
                stable_cycles = 0
                max_wait_secs = 180 

                while time.time() - poll_start < max_wait_secs:
                    await page.wait_for_timeout(1000)
                    
                    if custom_resp:
                        try:
                            new_text = await active_root.locator(custom_resp).last.inner_text()
                        except Exception:
                            new_text = ""
                    else:
                        try:
                            if await active_root.locator("div[data-testid='stMarkdownContainer']").count():
                                new_text = await active_root.locator("div[data-testid='stMarkdownContainer']").last.inner_text()
                            elif await active_root.locator("main").count():
                                new_text = await active_root.locator("main").inner_text()
                            else:
                                new_text = await active_root.locator('body').inner_text()
                        except Exception:
                            new_text = ""

                    lower_text = new_text.lower()
                    
                    # 1. Error fast-exit (for financial-agentt crashes)
                    is_error_state = any(err in lower_text for err in ERROR_TERMINAL_PATTERNS)
                    
                    # 2. Threshold determination (exact match from your old working code)
                    current_threshold = cfg.get('stable_seconds', 8)
                    if is_error_state:
                        current_threshold = 2
                    elif any(kw in lower_text for kw in ['wait', 'executing', 'analyzing', 'researching', 'scanning', 'synthesizing', 'progress']):
                        current_threshold = 60

                    # 3. Stabilization accounting
                    if len(new_text.strip()) > len(before_text.strip()) or is_error_state:
                        if new_text.strip() == current_text.strip():
                            stable_cycles += 1
                            if stable_cycles >= current_threshold:
                                break
                        else:
                            current_text = new_text
                            stable_cycles = 0

                after = current_text if current_text else (await active_root.locator('body').inner_text())
                last_text = after.strip()
                transcript.append({'user': turn, 'agent': last_text[:8000]})
                
                if is_error_state:
                    break

            await b.close()

        return {
            'text': last_text[-8000:],
            'latency_ms': (time.perf_counter() - start) * 1000,
            'evidence': {
                'adapter': 'browser',
                'url': target.base_url,
                'page_errors': errs[:10],
                'turns': len(turns),
                'transcript': transcript
            },
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