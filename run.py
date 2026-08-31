from __future__ import annotations

import uvicorn

import settings

if __name__ == "__main__":
    uvicorn.run(
        "app:app",
        host=settings.HOST,
        port=settings.PORT,
        workers=1,
        proxy_headers=True,
        forwarded_allow_ips="127.0.0.1",
        log_level="info",
        access_log=True,
    )
