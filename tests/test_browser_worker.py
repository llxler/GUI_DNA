from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager
from threading import Barrier, Lock

import pytest

from studies.browser_worker import reentrant_slots


def test_nested_browser_work_holds_one_slot_per_thread_and_releases_on_error():
    lock = Lock()
    overlap = Barrier(2, timeout=3)
    held = total = peak = 0

    @contextmanager
    def reserve():
        nonlocal held, total, peak
        with lock:
            total += 1
            held += 1
            peak = max(held, peak)
        try:
            yield
        finally:
            with lock:
                held -= 1

    slot = reentrant_slots(reserve)

    def one():
        with pytest.raises(ValueError), slot(), slot():
            overlap.wait()
            raise ValueError("page closed")
        with slot(), slot():
            pass

    with ThreadPoolExecutor(max_workers=2) as pool:
        list(pool.map(lambda _: one(), range(2)))
    assert (held, total, peak) == (0, 4, 2)
