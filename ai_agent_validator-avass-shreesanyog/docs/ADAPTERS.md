# Universal adapter strategy
A website URL is not an agent protocol. AVaaS uses adapters:
1. Browser: Playwright discovers visible inputs/buttons and drives the actual UI. Optional selectors improve reliability.
2. OpenAPI: finds `/openapi.json` or `/swagger.json` and enumerates operations.
3. REST mapping: reserved for custom templates when an API exists but is undocumented.
4. Transcript: validation-only mode for CAPTCHA, SSO, anti-bot, canvas-rendered or inaccessible interfaces.
Discovery is evidence, not a claim of full compatibility. A run fails explicitly when it cannot find an interaction surface.
