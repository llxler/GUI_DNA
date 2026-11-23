"""Reconstruct the original library baseline using the same response-only recovery rule."""
import argparse
from studies.compatible_library_rebuild.sealed_evaluate_20261123 import REPORT as REBUILDS
from studies.compatible_table_local_plans.evaluate import RESULT as PLANS
from studies.study_io import ROOT, dump, read, sha

OUTPUT = ROOT / 'studies/results/table-local-original-recovery-20261123.json'


def reconstruct():
    local = read(PLANS)
    fixed = read(REBUILDS)['fixed_documentation_example_1']['targets']['original']
    rows={}
    for task,entry in local['targets'].items():
        active = entry['received'] and 'original' not in entry['pages']
        strict = entry['passed']['original']
        rows[task]={'strict':strict,'use_example':active,'fixed':fixed[task]['passed'],
                    'recovered':fixed[task]['passed'] if active else strict}
    return {'project':'table','builder':'openai/gpt-5','planner':local['model'],
            'rule':'Retain every valid first plan, including failing pages. Use example one only when a response is received but does not compile. Missing responses remain missing.',
            'observed':sum(r['strict'] is not None for r in rows.values()),
            'totals':{k:sum(r[k] is True for r in rows.values()) for k in ('strict','use_example','fixed','recovered')},
            'targets':rows,'inputs':{str(p.relative_to(ROOT)):sha(p) for p in (REBUILDS,PLANS)}}


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--check',action='store_true')
    args=parser.parse_args()
    report=reconstruct()
    if args.check or OUTPUT.exists():
        assert read(OUTPUT)==report
    else:
        dump(OUTPUT,report)
    print(report['totals'])
