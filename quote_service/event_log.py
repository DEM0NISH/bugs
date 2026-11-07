import json
import threading
from pathlib import Path
from queue import Queue


class JsonlEventWriter:
    def __init__(self, path: str | Path):
        self.path = Path(path)
        self.events = Queue()
        self.lock = threading.Lock()
        self.closed = False
        self.thread = None

    def emit(self, event: dict) -> None:
        with self.lock:
            if self.closed:
                raise RuntimeError("Event writer is closed.")
            if self.thread is None:
                self.thread = threading.Thread(target=self._write, daemon=True)
                self.thread.start()
            self.events.put_nowait(event)

    def _write(self) -> None:
        with self.path.open("a", encoding="utf-8") as stream:
            while True:
                event = self.events.get()
                try:
                    if event is None:
                        stream.flush()
                        return
                    stream.write(json.dumps(event, default=str) + "\n")
                finally:
                    self.events.task_done()

    def close(self) -> None:
        with self.lock:
            if self.closed:
                return
            self.closed = True
            thread = self.thread
            if thread is not None:
                self.events.put_nowait(None)
        if thread is not None:
            thread.join()
