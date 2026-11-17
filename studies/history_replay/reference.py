"""Correct the legacy-rule/positive-reference label before any candidate grading."""
import argparse
from . import run
from test.webbench_dna import domain, evaluate
from test.webbench_dna.library import library


def prepare():
    assert not (run.OUT/'grading-started.json').exists()
    assert not (run.OUT/'reference-extension.json').exists()
    task=domain.tasks()[-1]
    lib=library()
    plan=domain.reference_plan(task['features'])
    script=domain.compile_plan(plan,task['features'],lib)
    page=run.OUT/'positive-reference'
    evaluate.write_candidate(page,script=script)
    run.dump(page/'plan.json',plan)
    paths=[run.HERE/'reference.py',run.HERE/'REFERENCE.md',page/'plan.json',page/'index.html',page/'candidate.js']
    paths += [run.ROOT/'test/webbench_dna'/p for p in ('domain.py','evaluate.py','library.py','shell.html')]
    paths += [run.ROOT/'test/results/prefix-history-audit.json']
    job={'harness':'expert-dom1','runtime':'163','project':'dom1','page':str(page.relative_to(run.ROOT)),
         'files':run.source_files(page,True),'specs':['init',*[f'task-{i}' for i in range(1,21)]],'all_tests':True}
    run.dump(run.OUT/'reference-extension.json',{'frozen_utc':run.now(),'inputs_sha256':run.digest(run.read(run.OUT/'inputs.json')),
        'sha256':{str(p.relative_to(run.ROOT)):run.sha(p) for p in paths},'job':job,
        'correction':'Initial expert calibration page was the historical deliberately naive rule control, not the positive reference. No candidate grading had begun.'})


def verify():
    value=run.read(run.OUT/'reference-extension.json')
    for p,s in value['sha256'].items():
        assert run.sha(run.ROOT/p)==s,p
    assert value['inputs_sha256']==run.digest(run.read(run.OUT/'inputs.json'))
    return value


def calibrate():
    value=verify()
    score=run.grade('expert-dom1/positive-reference',value['job'],True)
    assert score['all_passed'], 'Keep reference failures; do not silently tune'
    run.dump(run.OUT/'reference-extension-complete.json',{'finished_utc':run.now(),'extension_sha256':run.digest(value),
                                                        'all_passed':True,'report_sha256':score['report_sha256']})
    print('Positive final reference: all 21 files passed',flush=True)


def evaluate_all():
    value=verify()
    complete=run.read(run.OUT/'reference-extension-complete.json')
    assert complete['extension_sha256']==run.digest(value) and complete['all_passed']
    assert value['frozen_utc'] <= complete['finished_utc']
    run.evaluate()


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('phase',choices=['prepare','calibrate','evaluate'])
    {'prepare':prepare,'calibrate':calibrate,'evaluate':evaluate_all}[parser.parse_args().phase]()
