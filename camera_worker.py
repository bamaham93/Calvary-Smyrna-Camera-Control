"""Serializes all camera I/O through a single background thread.

VISCA talks to the camera over a single UDP "line" that behaves like a
serial interface: one command at a time, in order. There's nothing to gain
from letting multiple web requests hit the socket concurrently, and real
risk of two threads racing on the same recvfrom() call. Routes submit a
job here instead of calling the camera directly, so a slow or hung camera
command stalls only this worker thread — never the web server, and never
a browser waiting past `timeout` on the HTTP response.
"""

import queue
import threading


class TimedOut(Exception):
    """A submitted camera command didn't finish within its timeout."""


class CameraWorker:
    def __init__(self):
        self._queue = queue.Queue()
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    def _run(self):
        while True:
            func, args, kwargs, done, box = self._queue.get()
            try:
                box["result"] = func(*args, **kwargs)
            except Exception as exc:
                box["error"] = exc
            finally:
                done.set()

    def submit(self, func, *args, wait=True, timeout=2.0, **kwargs):
        """Queue a camera call to run on the worker thread.

        If `wait` (default), blocks for up to `timeout` seconds for the
        call to finish and returns its result, re-raising any exception it
        raised, or raises TimedOut if it hasn't finished in time. If not
        `wait`, enqueues and returns immediately without waiting.
        """
        done = threading.Event()
        box = {}
        self._queue.put((func, args, kwargs, done, box))

        if not wait:
            return None

        if not done.wait(timeout):
            raise TimedOut(f"Camera command timed out after {timeout}s")

        if "error" in box:
            raise box["error"]
        return box.get("result")
