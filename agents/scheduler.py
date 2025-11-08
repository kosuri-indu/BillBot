import threading
import time

_thread = None

def _run_loop(period_minutes: int):
    # Lightweight no-op loop so the app's scheduler call does not fail.
    while True:
        try:
            # In future this can trigger background agent runs.
            time.sleep(period_minutes * 60)
        except Exception:
            time.sleep(60)

def start(period_minutes: int = 15):
    global _thread
    if _thread and _thread.is_alive():
        return
    _thread = threading.Thread(target=_run_loop, args=(period_minutes,), daemon=True)
    _thread.start()
