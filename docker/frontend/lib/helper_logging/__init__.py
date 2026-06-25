from __future__ import annotations

import time

def debug(message: str) -> None:
    timestamp = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime())
    print(f"DEBUG: {timestamp} - {message}")
