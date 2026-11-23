"""Count distinct Web-Bench project–task positions by library source across protocols."""
import argparse
import subprocess
from collections import defaultdict

from studies.study_io import ROOT, UPSTREAM, dump, read, sha

RESULTS = ROOT / 'studies/results'
OUTPUT = RESULTS / 'webbench-coverage-20261123.json'
CATALOG = 'https://arxiv.org/html/2505.07473v1#A1'


def reconstruct():
    source_paths = []
    def use(name):
        path = ROOT / name
        source_paths.append(path)
        return read(path)
    positions = {k: defaultdict(set) for k in ('human', 'ai')}

    def add(source, project, task):
        n = int(str(task).removeprefix('task-'))
        assert 1 <= n <= 20
        positions[source][project].add(n)

    base = use('studies/results/end_to_end.json')
    for r in base['records']:
        if r['method'] == 'plan' and r['current'] is not None:
            add('ai', r['project'], r['task'])
    for cohort in [*base['canvas_pilots'].values(), base['matched_flex']]:
        for name, row in cohort['rows'].items():
            if name.startswith('plan-') and row['status'] != 'build_failure' and row['passed'] is not None:
                add('ai', cohort['project'], name.split('/')[1])
    dom = use('studies/webbench_dna/results/summary.json')
    for model in dom['models']:
        if model['model'] == 'google/gemma-3-12b-it':
            continue
        for r in model['rows']:
            if r.get('dna') is not None and r['dna']['final_all'] is not None:
                add('human', 'dom1', r['task'])
    def include(project, cells, human_key):
        for method, key in [('human', human_key), ('ai', 'ai')]:
            for n, value in cells[key].items():
                if value['passed'] is not None:
                    add(method, project, n)
    for project, cohort in use('studies/results/library-sources-20261121.json').items():
        include(project, cohort['cells'], 'reference')
    chart = use('studies/results/svg-chart-interfaces-20261123.json')
    include('svg-chart', chart['cells'], 'reference_typed')
    for project, file in [('table', 'table-library-sources'), ('expression-editor', 'expression-editor-sources')]:
        record = use('studies/results/' + file + '-20261123.json')
        for n, arms in record['targets'].items():
            for key, source in [('reference', 'human'), ('ai', 'ai')]:
                if any(arms[key][phase]['passed'] is not None for phase in ('first', 'after_public_repair')):
                    add(source, project, n)

    heldout = use('studies/results/expression-editor-unseen-20261123.json')
    for task, groups in heldout['targets'].items():
        if any(groups['ai'][phase]['status'] in ('scored', 'invalid_response') for phase in ('first', 'final')):
            add('ai', 'expression-editor', task)
    window = use('studies/results/expression-editor-window-20261123.json')
    for task, groups in window['targets'].items():
        if any(groups['ai'][phase]['received'] for phase in ('first', 'final')):
            add('ai', 'expression-editor', task)

    # A single-arm prompt diagnostic is not a new matched workflow; identify any additional observed targets explicitly.
    prompt_only = []
    extra_file = 'studies/results/expression-editor-interface-examples-20261123.json'
    if (ROOT / extra_file).exists():
        examples = use(extra_file)
        prompt_only = sorted(int(t.removeprefix('task-')) for t, r in examples['targets'].items()
                             if r['appended']['response'] and int(t.removeprefix('task-')) not in positions['human']['expression-editor'])

    revision = subprocess.check_output(['git', '-C', str(UPSTREAM), 'rev-parse', 'HEAD'], text=True).strip()
    assert revision == '7b31ca2b786eef120dd49ce63dd03d0c0006046d'
    extra = {'demo', 'project-template', 'pull-loading'}
    projects = {p.name: p for p in (UPSTREAM / 'projects').iterdir() if p.is_dir() and p.name not in extra}
    assert len(projects) == 50
    for p in projects.values():
        assert all((p / 'test' / f'task-{n}.spec.js').is_file() or
                   (p / 'test' / f'task-{n}.spec.ts').is_file() for n in range(1, 21)), p
    for group in positions.values():
        assert set(group) <= set(projects)
    return {'source_catalog': CATALOG, 'standalone_prompt_only_human_editor_tasks': prompt_only, 'projects': sorted(projects), 'project_count': len(projects),
            'target_count': len(projects) * 20, 'upstream_commit': revision,
            'unit': 'One project and current task file with an observed target outcome. A model response failing validation counts. '
                    'An invalid preparation without target responses is reported separately. Repeats, builders and control pages add no positions.',
            'sources': {k: {'projects': len(v), 'targets': sum(map(len, v.values())),
                            'by_project': {p: sorted(ts) for p, ts in sorted(v.items())}} for k, v in positions.items()},
            'inputs': {str(p.relative_to(ROOT)): sha(p) for p in source_paths}}


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--write', action='store_true')
    args = parser.parse_args()
    data = reconstruct()
    if args.write:
        dump(OUTPUT, data)
    else:
        assert read(OUTPUT) == data
    print({k: (v['projects'], v['targets']) for k, v in data['sources'].items()})
