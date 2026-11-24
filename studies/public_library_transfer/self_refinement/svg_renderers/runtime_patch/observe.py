"""Observe graphic primitives and uncaught or explicitly dispatched public browser errors."""
import re
from urllib.parse import urlsplit

from playwright.sync_api import Error as BrowserError, sync_playwright

from studies.public_library_transfer import browser
from .. import components as comp

PROBE = """
async selector => {
  const {configs} = await import('/assets/data.js');
  const drawn = {}, mounted = {};
  for (const [id, config] of Object.entries(configs)) {
    const el = document.getElementById(id);
    const ok = el instanceof SVGElement && !!el.closest('.root');
    mounted[config.type] = (mounted[config.type] || 0) + Number(ok);
    drawn[config.type] = (drawn[config.type] || 0) + (ok ? el.querySelectorAll(selector).length : 0);
  }
  return {drawn, mounted, caught:window.__domainStageErrors};
}
"""
WATCH = """
window.__domainStageErrors = [];
window.addEventListener('error', event => {
  if (event.error || event.message) {
    const stack = String(event.error?.stack || '').split('\u005cn').slice(1,3).join(' ');
    window.__domainStageErrors.push([String(event.message), stack]);
  }
}, true);
window.addEventListener('unhandledrejection', event =>
  window.__domainStageErrors.push([String(event.reason), 'unhandledrejection']));
"""


def observe(out, page, files):
    served = browser.served_page(out, comp.CHART, page, files)
    with browser.serve(comp.CHART, served) as url, sync_playwright() as pw:
        with pw.chromium.launch(env=browser.browser_env()) as engine:
            tab = engine.new_page(service_workers="block")
            tab.route("**/*", lambda r: r.continue_() if urlsplit(r.request.url).netloc in ("", urlsplit(url).netloc) else r.abort())
            tab.set_default_timeout(10000)
            tab.add_init_script(WATCH)
            errors = []
            tab.on("pageerror", lambda e: errors.append([str(e), ""]))
            try:
                tab.goto(url, wait_until="networkidle", timeout=18000)
                value = tab.evaluate(PROBE, comp.GRAPHICS)
            except BrowserError as e:
                zeros = dict.fromkeys(comp.KINDS, 0)
                value = {"drawn": zeros, "mounted": zeros, "caught": [[str(e).splitlines()[0], "page load"]]}
            notes = {}
            for msg, frame in value.pop("caught") + errors:
                msg = re.sub(r"https?://(?:localhost|127\.0\.0\.1):\d+", "", msg)[:320]
                frame = re.sub(r"https?://(?:localhost|127\.0\.0\.1):\d+", "", frame)[:400]
                if msg not in notes or not notes[msg]:
                    notes[msg] = frame
            return {**value, "errors": notes}


def accept(old, new):
    def positive(ob, key):
        return {k for k, n in ob[key].items() if n}
    for key in ("mounted", "drawn"):
        if not positive(old,key) <= positive(new,key):
            return False
    return (len(new["errors"]) <= len(old["errors"]) and
            (any(positive(old,k) < positive(new,k) for k in ("mounted","drawn")) or
             len(new["errors"]) < len(old["errors"])))
