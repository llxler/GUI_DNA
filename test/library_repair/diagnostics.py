"""Descriptive output-form and configuration-diversity checks, not semantic proofs."""
from collections import Counter
from .core import ROOT, CONDITIONS, read, dump, digest, source_output
from .core import MODELS, original_package, source_folder
from .run import library_folder
from test.webbench_expand.generate import output_files


def main():
    primary = read(ROOT / 'test/results/library-repair-available.json')
    forms, source_pages = Counter(), {}
    for row in primary['rows']:
        if row['kind'] != 'candidate' or row['condition'] != 'review' or row['format'] != 'strict':
            continue
        folder = ROOT / row['source']
        record = read(folder / 'record.json')
        if not record['versions']:
            source_pages[row['source']] = None
            forms[row['method'] + '/no_executable'] += 1
            continue
        parsed = source_output(folder)
        form = 'plan' if row['method'] == 'plan' else ('program' if 'program' in parsed else 'files')
        forms[row['method'] + '/' + form] += 1
        source_pages[row['source']] = read(folder / record['versions'][-1] / 'source-manifest.json')['output_sha256']
    diversity = []
    for label in ('strict', 'single_fence'):
        data = primary
        for pair in primary['selected_pairs']:
            project, builder = pair['project'], pair['builder']
            for condition in CONDITIONS:
                selected = [r for r in data['rows'] if (r['format'], r['kind'], r['method'], r['project'], r['builder'], r['condition']) == (label, 'candidate', 'plan', project, builder, condition)]
                plans = {digest(source_output(ROOT / r['source'])) for r in selected}
                before = {source_pages[r['source']] for r in selected if source_pages[r['source']] is not None}
                after = {r['files_sha256'] for r in selected if r['score_key']}
                diversity.append({'diagnostic': label, 'project': project, 'builder': builder,
                    'condition': condition, 'comparisons': len(selected), 'distinct_plans': len(plans),
                    'original_distinct_pages': len(before), 'revised_distinct_pages': len(after)})
    reuse = []
    original = original_package('table', 'openai/gpt-5')
    revised = read(library_folder('table', 'openai/gpt-5', 'feedback') / 'package.json')
    for model in MODELS:
        folder = source_folder('table', 'openai/gpt-5', model, 'free_lib', 20)
        parsed = source_output(folder)
        before = output_files('free_lib', original, parsed)
        after = output_files('free_lib', revised, parsed)
        row = next(r for r in primary['rows'] if r['format'] == 'strict' and r['kind'] == 'candidate'
                   and r['condition'] == 'feedback' and r['source'] == str(folder.relative_to(ROOT)))
        reuse.append({'model': model, 'form': 'program' if 'program' in parsed else 'files',
                      'overrides_index_js': 'index.js' in parsed.get('files', {}),
                      'index_js_changed': before.get('index.js') != after.get('index.js'),
                      'before_passed': row['baseline']['passed'], 'after_passed': row['passed']})
    result = {'output_forms': dict(forms), 'plan_page_diversity': diversity, 'table_task20_code_reuse': reuse,
              'table_feedback_compiler_unchanged': original['compiler'] == revised['compiler'],
              'scope': 'Byte-level diversity across stored configurations. Different bytes need not mean different behavior; '
                       'retaining variation does not establish that option semantics are preserved.'}
    dump(ROOT / 'test/results/library-repair-diagnostics.json', result)
    print(result['output_forms'])
    for row in diversity:
        if row['revised_distinct_pages'] < row['original_distinct_pages']:
            print('Reduced page diversity:', row)


if __name__ == '__main__':
    main()
