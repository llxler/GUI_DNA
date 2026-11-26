"""Expose user-visible state following an ordinary click, a different click and a context click."""
import json
import sys
from playwright.sync_api import sync_playwright
from studies.public_library_transfer import browser
from studies.study_io import ROOT
if __name__=='__main__':
    with browser.serve('table',ROOT/sys.argv[1]) as url,sync_playwright() as pw,pw.chromium.launch(env=browser.browser_env()) as eng:
        tab=eng.new_page(service_workers='block')
        tab.route('**/*',lambda r:r.continue_() if r.request.url.startswith(url+'/') else r.abort())
        tab.goto(url);cells=tab.locator('th,td')
        evidence=[]
        for i,button in [(4,'left'),(5,'left'),(5,'right')]:
            cells.nth(i).click(button=button,timeout=2500)
            evidence.append([i,button,tab.locator('.selected').all_text_contents(),tab.locator('.menu:visible').count(),tab.locator('tbody tr').count(),tab.locator('thead th').count()])
        print(json.dumps(evidence))
