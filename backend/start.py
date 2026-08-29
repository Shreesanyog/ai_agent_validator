import sys
import asyncio
import uvicorn

# Force Windows to use the correct background-task loop BEFORE the server starts
if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())

if __name__ == "__main__":
    uvicorn.run("app.main:app", host="127.0.0.1", port=8000)