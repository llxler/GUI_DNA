"""Check long-window preparation receipts, frozen target artifacts and official scores."""
import argparse
from collections import defaultdict

from studies.expression_editor_unseen_requirements.report import score_value
from studies.ledger_read import calls, totals
from studies.study_io import ROOT, digest, dump, read, sha, source_files
from studies.table_library_sources.run import verify

from .run import OLD, OUT, core, runner

OUTPUT = ROOT / 'studies/results/expression-editor-window-20261123.json'


def reconstruct():
    if (OUT / 'not-started.json').exists():
        assert not (OUT / 'budget.sqlite3').exists() and not (OUT / 'freeze.json').exists()
        state = read(OUT / 'not-started.json')
        assert state['available_stage_usd'] < .35
        return {'project':core.PROJECT, 'status':'registered_not_run', 'reason': state['reason'],
                'targets':{}, 'study_model_calls':0, 'registration_sha256':sha(OUT / 'registration.json')}
    stages = ('freeze', 'preparation-complete', 'planning-freeze', 'generation-complete', 'scores-complete')
    study = {s: read(OUT / (s + '.json')) for s in stages}
    for marker in study.values():
        verify(marker['inputs_sha256'])
    prep = study['preparation-complete']['arms']
    gen = {(a, t, s): rec for a, t, s, rec in study['generation-complete']['rows']}
    available = {a for a in runner.ARMS if prep[a]['first']['valid']}
    assert available == set(study['planning-freeze']['available'])
    assert len(gen) == len(study['generation-complete']['rows'])
    first_keys = {(a, t, 'first') for a in available for t in core.TASKS}
    assert {key for key in gen if key[2] == 'first'} == first_keys
    repair_keys = {(a, t, 'repair') for a, t, stage in first_keys if gen[a, t, stage]['received'] and not gen[a, t, stage]['valid']}
    assert set(gen) == first_keys | repair_keys
    for (a, t, stage), rec in gen.items():
        assert read(OUT / 'candidates' / a / t / stage / 'record.json') == rec
    scores = study['scores-complete']['rows']
    expected_scores = {'/'.join(k) for k, rec in gen.items() if rec['valid']}
    if 'ai' in available:
        expected_scores.update('fixed/' + t for t in core.TASKS)
    assert set(scores) == expected_scores
    ledger = {r['id']: r for r in calls(OUT / 'budget.sqlite3')}
    seen, costs = set(), defaultdict(list)
    building = {}
    targets = {t: {} for t in core.TASKS}
    for a in runner.ARMS:
        f = OUT / 'preparation' / a / 'first'
        record = prep[a]['first']
        assert set(prep[a]) == {'first'}
        building[a] = {'received': record['received'], 'valid': record['valid'], 'error': record.get('error')}
        artifact = read(OUT / 'preparation' / a / 'artifact.json') if record['valid'] else None
        for phase, folder in [('preparation', f), ('target', OUT / 'candidates' / a)]:
            for p in folder.rglob('request.json'):
                req = read(p)
                where = p.parent.parent
                original = (core.preparation(a) if phase == 'preparation' else
                            core.target_prompt(a, where.parent.name, artifact))
                expected = original if where.name == 'first' else runner.repaired_prompt(where.parent / 'first')
                assert req['body']['messages'] == expected and read(where / 'record.json')['prompt_sha256'] == digest(expected)
                assert req['body']['model'] == (core.BUILDER if phase == 'preparation' else core.MODEL)
                assert req['body']['max_tokens'] == (32000 if phase == 'preparation' else 8192)
                rid = req['call_id']
                assert rid not in seen and rid in ledger
                seen.add(rid)
                costs[a, phase].append(ledger[rid])
        for t in core.TASKS:
            states = {}
            for name, ph in [('first', 'first'), ('final', 'repair' if (a, t, 'repair') in gen else 'first')]:
                rec = gen.get((a, t, ph))
                state = {'received': bool(rec and rec['received']), 'valid': bool(rec and rec['valid']), 'passed': None}
                if rec and rec['received']:
                    state['passed'] = False
                if rec and rec['valid']:
                    key = '/'.join((a, t, ph))
                    assert source_files(OUT / 'candidates' / key / 'page') == rec['files_sha256']
                    state['passed'] = score_value(OUT, 'scores', key, t, scores[key])
                    state['report_sha256'] = scores[key]['report_sha256']
                if artifact is None:
                    assert rec is None
                states[name] = state
            targets[t][a] = states
    assert seen == set(ledger)
    counts = {}
    for phase in ('first', 'final'):
        shared = [t for t in core.TASKS if all(targets[t][a][phase]['passed'] is not None for a in runner.ARMS)]
        counts[phase] = {'common': shared,
            'passed': {a: sum(targets[t][a][phase]['passed'] for t in shared) for a in runner.ARMS},
            'all_observed': {a: sum(r[a][phase]['passed'] is not None for r in targets.values()) for a in runner.ARMS},
            'all_passed': {a: sum(r[a][phase]['passed'] is True for r in targets.values()) for a in runner.ARMS}}
    fixed = {}
    if building['ai']['valid']:
        for task in core.TASKS:
            key = 'fixed/' + task
            fixed[task] = score_value(OUT, 'calibration', key, task, scores[key])
    billing = {a: {p: {'calls': len(costs[a, p]), 'settled_usd': sum(r['actual'] or 0 for r in costs[a, p])/1e6,
                         'exposure_usd': sum(r['actual'] if r['actual'] is not None else r['reserved'] for r in costs[a, p])/1e6}
                   for p in ('preparation', 'target')} for a in runner.ARMS}
    return {'project': core.PROJECT, 'preparation_scope': 'All twenty public requirements and public starter',
            'preparation_max_tokens': 32000, 'preparation_attempts_per_arm': 1, 'preparations': building,
            'builder': core.BUILDER, 'generator': core.MODEL, 'targets': targets, 'summaries': counts,
            'fixed_ai_example': fixed, 'billing': billing, 'ledger': totals(OUT / 'budget.sqlite3'),
            'stage_sha256': {s: sha(OUT / (s + '.json')) for s in ('registration', *stages)},
            'parent_calibration': sha(OLD / 'controls-complete.json')}


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--write', action='store_true')
    args = parser.parse_args()
    data = reconstruct()
    if args.write:
        if OUTPUT.exists():
            assert read(OUTPUT) == data
        dump(OUTPUT, data)
    else:
        assert read(OUTPUT) == data
    print({k: data[k] for k in ('status', 'preparations', 'summaries', 'ledger') if k in data})
