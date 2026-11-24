"""Recover and assemble already generated single-feature React modules offline."""
import argparse
from concurrent.futures import ThreadPoolExecutor
from functools import lru_cache
import hashlib
import json
from pathlib import Path
import re
import subprocess

from studies.study_io import ROOT, digest, dump, now, read, sha
from studies.public_library_transfer.other_benchmarks import evaluate
from studies.public_library_transfer.other_benchmarks.duo_original_results import bundle

HERE = Path(__file__).resolve().parent
OUT = ROOT / 'artifacts/duo-component-replay-20261124'
ORIGINAL = ROOT / 'artifacts/backbone-suites-20261124'
EXTRA = ROOT / 'artifacts/public-library-transfer-extra-20261123'
OLD = ROOT / 'studies/results/backbone-suites-20261124.json'
OVERLAP = ROOT / 'studies/results/public-library-transfer-duo-public-admission-20261123.json'
RESULT = HERE / 'result.json'
MODELS = {
    'qwen': 'qwen/qwen3-coder-30b-a3b-instruct', 'qwen9': 'qwen/qwen3.5-9b',
    'oss': 'openai/gpt-oss-120b', 'mistral': 'mistralai/mistral-small-3.2-24b-instruct',
    'gemma': 'google/gemma-3-12b-it', 'deepseek-flash': 'deepseek/deepseek-v4-flash',
}
GROUPS = ('blogging', 'taskmanagement')
ARMS = ('matched', 'fixed')


def words(value):
    expanded = re.sub(r'([a-z0-9])([A-Z])', r'\1 \2', value)
    return set(re.findall(r'[a-z0-9]+', expanded.lower()))


def endpoints(value):
    return set(re.findall(r'/api/[A-Za-z0-9_/-]+', value))


def score_feature(name, brief, component):
    id_words = words(component['id'])
    feature = words(name)
    source_urls = endpoints(component['source'])
    brief_urls = endpoints(brief)
    return (1_000_000 * (component['id'].casefold() == name.casefold())
            + 10_000 * len(brief_urls & source_urls)
            + 10 * len(feature & id_words) + len(feature & words(component['behavior'])))


def assign(briefs, entries):
    names = sorted(briefs)
    # The sentinel follows all source indices so an equal score prefers the first candidate.
    missing = len(entries)
    weights = [[score_feature(name, briefs[name], e) for e in entries] for name in names]

    @lru_cache(None)
    def best(i, used):
        if i == len(names):
            return 0, ()
        value, tail = best(i + 1, used)
        choices = [(value, (missing, *tail))]
        for j, weight in enumerate(weights[i]):
            if weight > 0 and not (used & (1 << j)):
                value, tail = best(i + 1, used | (1 << j))
                choices.append((weight + value, (j, *tail)))
        return min(choices, key=lambda pair: (-pair[0], pair[1]))

    return {name: entries[j]['id'] if j != missing else None
            for name, j in zip(names, best(0, 0)[1], strict=True)}


def inputs():
    return {task: row for task, row in read(EXTRA/'targets.json').items() if row['group'] in GROUPS}


def tracked():
    return [HERE/'run.py', HERE/'extract.cjs', HERE/'PROTOCOL.md', OLD, OVERLAP,
            Path(evaluate.__file__), Path(bundle.__code__.co_filename),
            EXTRA/'build-inputs.json', EXTRA/'targets.json', ORIGINAL/'registered.json',
            *(ORIGINAL/tag/'build'/group/'call/response.json' for tag in MODELS for group in GROUPS)]


def paths_digest():
    return {str(p.relative_to(ROOT)): sha(p) for p in tracked()}


def register():
    marker = OUT/'seal.json'
    hashes = paths_digest()
    if marker.exists():
        assert read(marker)['sources'] == hashes
        return
    tasks = inputs()
    briefs = read(EXTRA/'build-inputs.json')
    libraries, candidates = {}, {}
    for tag in MODELS:
        libraries[tag] = {}
        candidates[tag] = {}
        for group in GROUPS:
            response = read(ORIGINAL/tag/'build'/group/'call/response.json')
            text = response['choices'][0]['message'].get('content') or ''
            data = subprocess.run(['node', str(HERE/'extract.cjs')], input=json.dumps(text),
                                  text=True, capture_output=True, check=True, cwd=ROOT)
            result = json.loads(data.stdout)
            entries = result['delivered']
            mapping = assign(briefs[group], entries)
            libraries[tag][group] = {
                'mapping': mapping, 'rejected': result['rejected'], 'components': [
                    {k: e[k] for k in ('id', 'format')} |
                    {'source_sha256': hashlib.sha256(e['source'].encode()).hexdigest()} for e in entries
                ],
            }
            library = {'components': entries}
            for task, row in tasks.items():
                if row['group'] != group:
                    continue
                module = row['public']['module']
                names = module.split('_')
                assert len(names) == 2 and all(n in briefs[group] for n in names)
                arms = candidates[tag][task] = {}
                for arm, ids in [('matched', [mapping[n] for n in names]),
                                 ('fixed', [e['id'] for e in entries[:2]])]:
                    if not ids or None in ids:
                        arms[arm] = {'status': 'missing_component'}
                        continue
                    config = {'first': ids[0], 'second': ids[1] if len(ids) == 2 else 'NONE'}
                    files = bundle(module, library, config)
                    path = OUT/'candidates'/tag/task/(arm+'.json')
                    dump(path, files)
                    arms[arm] = {'status': 'assembled', 'config': config, 'files_sha256': sha(path)}
    dump(marker, {'utc': now(), 'sources': hashes, 'libraries': libraries, 'candidates': candidates})


def report(workers):
    marker = OUT/'seal.json'
    seal = read(marker)
    assert seal['sources'] == paths_digest()
    tasks = inputs()
    old = read(OLD)
    records = {}
    jobs = {}
    for tag, model in MODELS.items():
        rows = records[model] = {}
        acquired = old['models'][model]
        assert acquired['seal_sha256'] == sha(ORIGINAL/tag/'seal.json')
        by_cell = {(r['task'], r['arm']): r for r in acquired['rows']}
        for task, arms in seal['candidates'][tag].items():
            row = rows[task] = {'group': tasks[task]['group']}
            for arm in ('direct', 'self'):
                original = by_cell[task, arm]
                row[arm] = {k: original[k] for k in ('status', 'passed', 'report_sha256') if k in original}
            for arm, item in arms.items():
                entry = row[arm] = dict(item)
                if item['status'] != 'assembled':
                    entry['passed'] = False
                    continue
                path = OUT/'candidates'/tag/task/(arm+'.json')
                assert item['files_sha256'] == sha(path)
                key = (task, sha(path))
                if key not in jobs:
                    jobs[key] = (tasks[task], path, [])
                jobs[key][2].append(entry)

    def grade(item):
        (task, checksum), (target, path, entries) = item
        folder = OUT/'scores'/task/checksum
        verdict = evaluate.score((target['group'], target, read(path), folder, None))
        assert verdict['report_sha256'] == sha(folder/'jest.json')
        for entry in entries:
            entry.update(passed=verdict['passed'], report_sha256=verdict['report_sha256'],
                         official_cases_passed=verdict['assertion_statuses'].count('passed'))
    with ThreadPoolExecutor(max_workers=workers) as pool:
        list(pool.map(grade, jobs.items()))
    result = {'study': 'Offline public-feature recovery and explicit composition',
              'fresh_model_calls': 0, 'registered_utc': seal['utc'], 'seal_sha256': sha(marker),
              'sources': seal['sources'], 'libraries': {MODELS[t]: v for t, v in seal['libraries'].items()},
              'rows': records, 'totals': totals(records)}
    dump(RESULT, result)


def totals(records):
    out = {}
    for model, rows in records.items():
        assert len(rows) == 10
        keys = ['direct', 'self', *ARMS]
        common = [t for t, r in rows.items() if all(r[a]['passed'] is not None for a in keys)]
        out[model] = {'common_targets': common, **{a: sum(rows[t][a]['passed'] for t in common) for a in keys},
                      'only_matched': [t for t in common if rows[t]['matched']['passed'] and not rows[t]['direct']['passed']],
                      'only_direct': [t for t in common if rows[t]['direct']['passed'] and not rows[t]['matched']['passed']]}
    return out


def check():
    data = read(RESULT)
    assert data['totals'] == totals(data['rows'])
    old = read(OLD)['models']
    assert data['sources'][str(OLD.relative_to(ROOT))] == sha(OLD)
    assert data['sources'][str(OVERLAP.relative_to(ROOT))] == sha(OVERLAP)
    for path in (HERE/'run.py', HERE/'extract.cjs', HERE/'PROTOCOL.md'):
        assert data['sources'][str(path.relative_to(ROOT))] == sha(path)
    for model in MODELS.values():
        assert set(data['rows'][model]) == {r['task'] for r in old[model]['rows'] if r['group'] in GROUPS}
        for row in old[model]['rows']:
            if row['group'] in GROUPS and row['arm'] in ('self', 'direct'):
                actual = data['rows'][model][row['task']][row['arm']]
                assert actual['passed'] == row['passed'] and actual.get('report_sha256') == row.get('report_sha256')
        for row in data['rows'][model].values():
            for arm in ARMS:
                outcome = row[arm]
                if outcome['status'] == 'assembled':
                    assert outcome['passed'] == (outcome['official_cases_passed'] == 4)
                else:
                    assert outcome == {'status': 'missing_component', 'passed': False}
    print(json.dumps({k: {a: v[a] for a in ['direct', 'self', *ARMS]} for k,v in data['totals'].items()}))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=('register', 'score', 'check'))
    parser.add_argument('--workers', default=3, type=int)
    opts = parser.parse_args()
    if opts.action == 'register':
        register()
    elif opts.action == 'score':
        report(opts.workers)
    else:
        check()
