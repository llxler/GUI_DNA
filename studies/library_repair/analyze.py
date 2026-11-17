"""Read-only reconstruction and provenance audit of the implementation intervention."""
from collections import Counter, defaultdict
import hashlib
import json

from test.ledger_read import totals, calls
from .core import (ROOT, OUT, PROJECTS, BUILDERS, MODELS, CONDITIONS, read, dump,
                   digest, messages_for, original_package)
from .run import library_folder, verify_frozen

RESULT = ROOT / 'test/results/library-repair.json'


def summary(rows):
    return {'n': len(rows), 'baseline': sum(r['baseline']['passed'] for r in rows),
            'passed': sum(r['passed'] for r in rows),
            'wins': sum(r['passed'] and not r['baseline']['passed'] for r in rows),
            'losses': sum(r['baseline']['passed'] and not r['passed'] for r in rows),
            'compile_failures': sum(r['score_key'] is None for r in rows)}


def main():
    verify_frozen()
    snapshot = read(OUT / 'pre-scoring-snapshot.json')
    assert snapshot['frozen_utc'] <= read(OUT / 'grading-started.json')['started_utc']
    for path, sha in snapshot['sha256'].items():
        assert hashlib.sha256((ROOT / path).read_bytes()).hexdigest() == sha, path
    complete = read(OUT / 'evaluation-complete.json')
    inputs = read(OUT / 'replay-inputs.json')
    assert digest(inputs) == complete['inputs_sha256'] == read(OUT / 'grading-started.json')['inputs_sha256']
    generation = read(OUT / 'generation-complete.json')
    assert generation['finished_utc'] <= read(OUT / 'grading-started.json')['started_utc']
    public = read(OUT / 'public-inputs.json')
    used, providers, finishes, usage, libraries = [], Counter(), Counter(), defaultdict(Counter), []
    settled = {c['id']: c for c in calls(OUT / 'budget.sqlite3') if c['actual'] is not None}
    records = []
    for project in PROJECTS:
        for builder in BUILDERS:
            for condition in CONDITIONS:
                folder = library_folder(project, builder, condition)
                record, package = read(folder / 'record.json'), read(folder / 'package.json')
                records.append(record)
                assert record['status'] == 'complete' and record['valid_responses'] == 1
                assert digest(package) == record['package_sha256']
                original = original_package(project, builder)
                assert all(package[k] == original[k] for k in original if k not in ('files', 'compiler'))
                expected = messages_for(project, builder, condition, public[project][builder])
                assert read(folder / 'messages.json') == expected
                responses = []
                for request_path in (folder / 'call').rglob('request.json'):
                    request = read(request_path)
                    assert request['body']['messages'] == expected
                    if request['call_id'] not in settled:
                        continue
                    response = read(request_path.with_name('response.json'))
                    assert response['choices'][0]['message']['content'] == read(folder / 'output.json')['text']
                    responses.append(response)
                    used.append(request['call_id'])
                assert len(responses) == 1
                response = responses[0]
                providers[response.get('provider', 'unknown')] += 1
                finishes[response['choices'][0]['finish_reason']] += 1
                u = response['usage']
                key = condition + '/' + builder
                for field in ('prompt_tokens', 'completion_tokens', 'cost'):
                    usage[key][field] += u.get(field, 0)
                usage[key]['reasoning_tokens'] += u.get('completion_tokens_details', {}).get('reasoning_tokens', 0)
                libraries.append({**record, 'changed_package': package != original,
                    'original_files_bytes': sum(len(v.encode()) for v in original['files'].values()),
                    'files_bytes': sum(len(v.encode()) for v in package['files'].values()),
                    'original_compiler_bytes': len(original['compiler'].encode()),
                    'compiler_bytes': len(package['compiler'].encode()),
                    'response_usage': u, 'provider': response.get('provider'),
                    'finish_reason': response['choices'][0]['finish_reason']})
    assert digest(records) == generation['records_sha256']
    scores = {}
    for key, job in inputs['jobs'].items():
        folder = OUT / 'scores' / key
        score = read(folder / 'score.json')
        assert hashlib.sha256((folder / 'report.json').read_bytes()).hexdigest() == score['report_sha256']
        page = ROOT / job['page']
        files = {p.relative_to(page).as_posix(): p.read_text() for p in page.rglob('*') if p.is_file()}
        assert digest(files) == job['files_sha256']
        scores[key] = score
    rows = []
    for source in inputs['rows']:
        row = {**source, 'cohort': 'strong' if source['model'] == 'openai/gpt-5' else 'main'}
        row['passed'] = scores[row['score_key']]['all_passed'] if row['score_key'] else False
        rows.append(row)
    groups = []
    fields = ('kind', 'condition', 'cohort', 'project', 'builder', 'method')
    grouped = defaultdict(list)
    for row in rows:
        grouped[tuple(row[k] for k in fields)].append(row)
    for keys, selected in sorted(grouped.items()):
        groups.append({**dict(zip(fields, keys)), **summary(selected)})
    aggregates = []
    for kind in ('candidate', 'fixed', 'development'):
        for cohort in ('main', 'strong'):
            for condition in CONDITIONS:
                for method in ('plan', 'free_lib') if kind == 'candidate' else ('plan',):
                    selected = [r for r in rows if (r['kind'], r['cohort'], r['condition'], r['method']) == (kind, cohort, condition, method)]
                    if selected:
                        aggregates.append({'kind': kind, 'cohort': cohort, 'condition': condition, 'method': method, **summary(selected)})
    unchanged = [r for r in rows if r['unchanged_files']]
    mismatches = [r for r in unchanged if r['passed'] != r['baseline']['passed']]
    by_key = {(r['kind'], r['project'], r['builder'], r['model'], r['method'], r['task'], r['condition']): r for r in rows}
    contrasts = []
    for kind in ('candidate', 'fixed', 'development'):
        for cohort in ('main', 'strong'):
            for method in ('plan', 'free_lib') if kind == 'candidate' else ('plan',):
                selected = [r for r in rows if (r['kind'], r['cohort'], r['method'], r['condition']) == (kind, cohort, method, 'review')]
                pairs = [(r, by_key[(r['kind'], r['project'], r['builder'], r['model'], r['method'], r['task'], 'feedback')]) for r in selected]
                if pairs:
                    contrasts.append({'kind': kind, 'cohort': cohort, 'method': method, 'n': len(pairs),
                        'feedback_wins': sum(b['passed'] and not a['passed'] for a, b in pairs),
                        'feedback_losses': sum(a['passed'] and not b['passed'] for a, b in pairs)})
    result = {'scope': 'Posthoc fixed-output replay, not new planner generation or unseen-requirement transfer. '
              'Original schema/docs/examples retained; semantic equivalence is not guaranteed. '
              'Only three related projects; descriptive counts, no task-independent significance claim.',
              'aggregates': aggregates, 'groups': groups, 'rows': rows, 'libraries': libraries,
              'feedback_vs_review': contrasts, 'cost': totals(OUT / 'budget.sqlite3'),
              'usage': {k: dict(v) for k, v in usage.items()}, 'providers': dict(providers), 'finishes': dict(finishes),
              'audit': {'comparisons': len(rows), 'unique_browser_scores': len(scores),
                        'original_candidates': len({r['source'] for r in rows if r['kind'] == 'candidate'}),
                        'used_responses': len(used), 'frozen_files': len(read(OUT / 'review-manifest.json')['sha256']),
                        'pre_scoring_snapshot_files': len(snapshot['sha256']),
                        'unchanged_comparisons': len(unchanged), 'unchanged_score_mismatches': mismatches,
                        'generation_before_grading': True, 'original_scale_resumed': False}}
    dump(RESULT, result)
    lines = ['# 冻结接口下的实现修复与旧输出重放', '', result['scope'], '',
             '| 范围 | 规划者组 | 条件 | 做法 | 原库 | 修复后 | 改善/退步 |', '|---|---|---|---|---:|---:|---:|']
    for g in aggregates:
        lines.append(f"| {g['kind']} | {g['cohort']} | {g['condition']} | {g['method']} | {g['baseline']}/{g['n']} | {g['passed']}/{g['n']} | {g['wins']}/{g['losses']} |")
    lines += ['', '费用（USD）：' + json.dumps(result['cost']), '', '审计：' + json.dumps(result['audit'], ensure_ascii=False)]
    RESULT.with_suffix('.md').write_text('\n'.join(lines) + '\n')
    print('\n'.join(lines))


if __name__ == '__main__':
    main()
