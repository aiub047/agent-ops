"""
Entry point for the Agent-Ops API.

Run locally:
    python main.py
    # or
    uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

The APP_ENV environment variable controls which .env file is loaded:
    APP_ENV=local  →  .env.local
    APP_ENV=dev    →  .env.dev
    APP_ENV=prod   →  .env.prod
"""

import uvicorn


if __name__ == "__main__":
    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        log_level="info",
    )
