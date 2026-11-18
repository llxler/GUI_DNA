"""Apply the predeclared fixed-page and public-key probes to a separate library cohort."""
from pathlib import Path
from studies.study_io import ROOT, read, dump, sha
from studies.matched_canvas import browser
from studies.canvas_interface_probe import run as probe
from studies.canvas_fixed_reuse import run as reuse
from .run import OUT

RESULTS = ROOT/'studies/results'


def run_probes(stage, name):
    probe.MAIN = reuse.MAIN = browser.OUT = stage
    probe.OUT = ROOT/'artifacts'/f'{name}-probe'
    reuse.OUT = ROOT/'artifacts'/f'{name}-reuse'
    reuse.RESULT = RESULTS/f'{name}-reuse.json'
    # Same control pages and probe implementation as the initial calibration.
    original = ROOT/'artifacts/canvas-interface-probe-20261118'
    assert read(original/'freeze.json') == {p.name:sha(p) for p in (probe.HERE/'run.py',probe.HERE/'PROTOCOL.md')}
    probe.OUT.mkdir(parents=True,exist_ok=True)
    saved = original/'controls.json'
    if not (probe.OUT/'controls.json').exists():
        (probe.OUT/'controls.json').write_bytes(saved.read_bytes())
    assert sha(probe.OUT/'controls.json') == sha(saved)
    probe.main()
    raw = read(probe.OUT/'results.json')
    dump(RESULTS/f'{name}-probe.json',raw)
    reuse.freeze()
    reuse.evaluate()


if __name__ == '__main__':
    run_probes(OUT,'canvas-capacity-20261118')
