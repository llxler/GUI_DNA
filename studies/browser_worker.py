"""Run a registered study with one browser reservation per synchronous thread."""

from contextlib import contextmanager
import runpy
import sys
import threading
from unittest.mock import patch

from studies.public_library_transfer import browser


def reentrant_slots(acquire):
    """Nested page-server and browser contexts share the caller's reservation."""
    state = threading.local()

    @contextmanager
    def slot():
        if getattr(state, "held", False):
            yield
            return
        with acquire():
            state.held = True
            try:
                yield
            finally:
                state.held = False

    return slot


if __name__ == "__main__":
    module, *arguments = sys.argv[1:]
    if not module.startswith("studies."):
        raise SystemExit("Expected a studies module")
    sys.argv = [module, *arguments]
    with patch.object(browser, "browser_slot", reentrant_slots(browser.browser_slot)):
        runpy.run_module(module, run_name="__main__", alter_sys=True)
