"""Report slice probabilities and observed witnesses, without treating misses as impossibility."""
import hashlib
from collections import defaultdict
from .run import OUT, ROOT, PROJECTS, read, dump, digest, verify
from test.replay_library_repair import report_passed


def main():
    inputs = verify()
    for project in PROJECTS:
        assert read(OUT / f'evaluation-complete-{project}.json')['inputs_sha256'] == digest(inputs)
    scores, reused = {}, []
    for key, job in inputs['jobs'].items():
        folder = OUT / 'scores' / key
        score = read(folder / 'score.json')
        assert hashlib.sha256((folder / 'report.json').read_bytes()).hexdigest() == score['report_sha256']
        assert report_passed(read(folder / 'report.json')) == score['all_passed']
        scores[key] = score
        if (folder / 'reused.json').exists():
            reused.append(key)
    rows = [{**r, 'passed': bool(scores[r['score_key']]['all_passed']) if r['score_key'] else False} for r in inputs['rows']]
    groups = []
    historical = read(ROOT / 'test/results/webbench-expand-witnesses.json')
    old_witnesses = {(r['project'], r['builder'], int(t.removeprefix('task-'))) for r in historical['libraries'] for t in r['witness_tasks']}
    new_witnesses = []
    libraries = []
    for lib in inputs['libraries']:
        selected = [r for r in rows if (r['project'], r['builder']) == (lib['project'], lib['builder'])]
        by_mask = defaultdict(list)
        for row in selected:
            by_mask[row['mask']].append(row['passed'])
        libraries.append({**lib, 'comparisons': len(selected), 'passed': sum(r['passed'] for r in selected),
            'mean_tasks_passed': sum(r['passed'] for r in selected) / lib['sampled'],
            'best_sample_tasks': max(sum(v) for v in by_mask.values()),
            'anchor_tasks_passed': sum(next(r['anchor_baseline']['passed'] for r in selected if r['task'] == k) for k in (4, 8, 12, 16, 20)),
            'compile_failures': len({r['mask'] for r in selected if r['score_key'] is None}),
            'distinct_pages': len({r['score_key'].split('/')[-1] for r in selected if r['score_key']})})
        for task in (4, 8, 12, 16, 20):
            subset = [r for r in selected if r['task'] == task]
            passed = [r for r in subset if r['passed']]
            key = (lib['project'], lib['builder'], task)
            group = {'project': lib['project'], 'builder': lib['builder'], 'task': task,
                'n': len(subset), 'passed': len(passed), 'population': lib['population'],
                'exhaustive_slice': lib['exhaustive_slice'], 'anchor_passed': subset[0]['anchor_baseline']['passed'],
                'previous_witness': key in old_witnesses, 'witness': passed[0] if passed else None}
            groups.append(group)
            if passed and key not in old_witnesses:
                new_witnesses.append(group)
    result = {'scope': 'Boolean leaves present in one saved GPT-OSS final-plan anchor per library; nonboolean values and absent fields fixed. '
        'Three slices exhaustively enumerated, three uniformly sampled without replacement. Not uniform over the entire schema; '
        'best sample is an observed search witness, not a generation baseline. No cross-project significance claim.',
        'libraries': libraries, 'groups': groups, 'rows': rows, 'new_witnesses': new_witnesses,
        'historical_witness_pairs': historical['with_observed_witness'],
        'union_witness_pairs': historical['with_observed_witness'] + len(new_witnesses),
        'audit': {'configurations': sum(r['sampled'] for r in libraries), 'comparisons': len(rows),
                  'unique_reports': len(scores), 'reused_reports': len(reused), 'new_reports': len(scores) - len(reused)}}
    dump(ROOT / 'test/results/library-toggle-control.json', result)
    print(result['audit'])
    for lib in libraries:
        print(lib['project'], lib['builder'], 'slice', lib['sampled'], '/', lib['population'],
              'mean', lib['mean_tasks_passed'], 'anchor', lib['anchor_tasks_passed'], 'best', lib['best_sample_tasks'])
    print('new witnessed pairs', len(new_witnesses))


if __name__ == '__main__':
    main()
