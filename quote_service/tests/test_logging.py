import threading
from pathlib import Path


def test_log_writer_queues_without_waiting_for_file_io_and_flushes(tmp_path, monkeypatch):
    from quote_service.event_log import JsonlEventWriter

    path = tmp_path / "events.jsonl"
    write_started = threading.Event()
    release_write = threading.Event()
    enqueue_finished = threading.Event()
    original_open = Path.open

    def blocking_open(self, *args, **kwargs):
        if self == path:
            write_started.set()
            assert release_write.wait(timeout=5)
        return original_open(self, *args, **kwargs)

    monkeypatch.setattr(Path, "open", blocking_open)
    writer = JsonlEventWriter(path)

    def enqueue():
        writer.emit({"event": "queued"})
        enqueue_finished.set()

    producer = threading.Thread(target=enqueue)
    producer.start()
    assert write_started.wait(timeout=5)
    assert enqueue_finished.wait(timeout=5)
    release_write.set()
    writer.close()
    producer.join(timeout=5)
    assert not producer.is_alive()
    assert '"event": "queued"' in path.read_text(encoding="utf-8")
