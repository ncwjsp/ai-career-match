"""Keep long CPU work leased; lost ownership must stop publishing results."""

from contextlib import contextmanager
from threading import Event, Thread


class LostLease(RuntimeError):
    pass


@contextmanager
def keep_lease(queue, event_id, owner):
    stop = Event()
    lost = Event()

    def check():
        if lost.is_set() or not queue.renew(event_id, owner):
            raise LostLease("The analysis lease is no longer owned by this worker.")

    def renew():
        while not stop.wait(15):
            try:
                if not queue.renew(event_id, owner):
                    lost.set()
                    return
            except Exception:
                lost.set()
                return

    check()
    thread = Thread(target=renew, daemon=True)
    thread.start()
    try:
        yield check
        check()
    finally:
        stop.set()
        thread.join(timeout=2)
