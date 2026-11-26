"""Supply the archived target caller's original default token limit on resume."""
import argparse
import inspect
from unittest.mock import patch

from studies.study_io import ROOT, now, read, sha
from . import run


def resume(branch):
    old_request = run.original.request
    target_limit = inspect.signature(old_request).parameters["limit"].default
    receipt = run.OLD / run.TAG / "form/gpt5-library/1/call/request.json"
    assert read(receipt)["body"]["max_tokens"] == target_limit == 8192
    registration = run.OUT / "deployment-adapter.json"
    details = {"adapter_sha256": sha(__file__), "original_registration_sha256": sha(run.OUT / "registration.json"),
               "target_request_sha256": sha(receipt), "target_default": target_limit,
               "reason": "The original target calls request without a limit; the registered transport required it explicitly. No target request had been made."}
    with run.browser.lock(run.OUT / ".deployment-adapter.lock"):
        if not registration.exists():
            assert not list(run.OUT.glob("*/form/self/*/call/request.json"))
            run.core.save(registration, {"utc": now(), **details})
        assert all(read(registration)[k] == v for k, v in details.items())
    transport = run.send

    def send(tag, ledger, folder, messages, purpose, limit=target_limit):
        return transport(tag, ledger, folder, messages, purpose, limit)

    with patch.object(run, "send", send):
        run.generate(branch)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("branch", choices=run.BRANCHES)
    resume(parser.parse_args().branch)
