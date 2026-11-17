"""Check the local public-benchmark manuscript revision against saved evidence.

This is an editorial scope and selected-claim audit. It generates no candidates,
opens no writable budget ledger and does not rerun benchmark browsers.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import re

from test.paper_replay_coverage import PAPER, ROOT, table_inventory


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--report', type=Path,
                        default=ROOT / 'test/results/paper-public-review-20261116.json')
    args = parser.parse_args()
    sources, tables = table_inventory()
    texts = {name: (ROOT / name).read_text() for name in sources}
    content = '\n'.join(text for name, text in texts.items()
                        if Path(name).name != 'preamble.tex')
    ids = {row['id'] for row in tables}
    excluded = {
        'tab:round1', 'tab:round2', 'tab:list16', 'tab:list16-lib',
        'tab:heldout-main', 'tab:heldout-full', 'tab:heldout-usage',
        'tab:interaction-transfer', 'tab:interaction-library-shape',
        'tab:interaction-controls', 'tab:development-feedback',
        'tab:matched-feedback-main', 'tab:schema-search',
    }
    assert not ids & excluded, ids & excluded
    forbidden = (r'\listsuite', 'List-16', 'app:heldout', 'app:interaction-transfer',
                 'app:pilot', 'Development Primitives to Held-Out',
                 'Unseen synthetic combinations')
    assert not [term for term in forbidden if term in content]
    assert {'tab:main', 'tab:interface-main', 'tab:history-main',
            'tab:matched-feedback', 'tab:matched-feedback-usage'} <= ids

    data_sources = {}

    def load(name):
        path = ROOT / name
        data_sources[name] = digest(path)
        return json.loads(path.read_text())

    # Constant endpoints were removed from tables, not from the evidence.
    feedback = {}
    for model, name in (
        ('GPT-OSS-120B', 'test/results/matched-feedback.json'),
        ('GPT-5 medium', 'test/results/matched-feedback-frontier.json'),
    ):
        data = load(name)
        endpoints = {}
        for version in ('first', 'final'):
            for endpoint in ('withheld', 'history'):
                rows = [data['groups'][f'{method}/{version}/{endpoint}']
                        for method in ('free', 'free_lib', 'plan')]
                passed = sum(row['passed'] for row in rows)
                total = sum(row['total'] for row in rows)
                assert passed == 0
                endpoints[f'{version}/{endpoint}'] = {'passed': passed, 'total': total}
        feedback[model] = endpoints
    assert sum(value['final/history']['total'] for value in feedback.values()) == 45
    main_text = (PAPER / 'main.tex').read_text()
    feedback_text = (PAPER / 'public_feedback_audits.tex').read_text()
    assert 'None of the 45 final candidates passes' in main_text
    assert 'Neither the first nor final response passes' in feedback_text
    assert 'in any of the 45 candidates' in feedback_text

    search = load('test/results/schema-search.json')
    search_rows = []
    for library in search['libraries']:
        key = library['project'] + '/' + library['builder']
        current = search['groups'][key + '/current']
        history = search['groups'][key + '/history']
        assert history['passed'] == 0
        search_rows.append({
            'library': key, 'proposal_pool': library['population_size'],
            'selected': library['selected_count'], 'current': current, 'history': history,
        })
    assert sum(row['selected'] for row in search_rows) == 158
    assert sum(row['current']['passed'] for row in search_rows) == 12
    assert 'All 158 configurations fail full history.' in feedback_text
    assert 'Only BOM/Sonnet has current-file passes (12/32)' in feedback_text
    assert 'null' in feedback_text and 'early returns' in main_text

    # Recompute the new public-suite subtotal from the old explicit ledger rows.
    rows = load('test/results/table-details-replay.json')['original_costs']['rows']
    excluded_costs = {'Pilot round 1', 'Pilot round 2', 'List-16'}
    public_rows = [row for row in rows if row['study'] not in excluded_costs]
    public_cost = sum(row['settled_microusd'] for row in public_rows)
    assert public_cost == 11_945_801
    assert r'Public-suite subtotal & 11.95' in main_text
    assert r'\$14.36' not in content

    # The example is produced by the actual unchanged public-suite compiler.
    from test.todomvc_dna.domain import compile_plan, reference_plan, tasks
    from test.todomvc_dna.library import library
    task = next(task for task in tasks() if task['id'] == 'todo-03')
    plan = reference_plan(task['features'])
    compile_plan(plan, task['features'], library())
    formalism = (PAPER / 'supplied_formalism.tex').read_text()
    listings = re.findall(r'\\begin\{lstlisting\}[^\n]*\n(.*?)\\end\{lstlisting\}',
                          formalism, re.S)
    assert json.loads(listings[0]) == plan
    incomplete = json.loads(json.dumps(plan))
    del incomplete['handlers']['save']
    try:
        compile_plan(incomplete, task['features'], library())
    except ValueError as error:
        diagnostic = str(error)
    else:
        raise AssertionError('Missing save binding was accepted')
    assert listings[1].strip() == diagnostic
    alternative = json.loads(json.dumps(plan))
    alternative['handlers']['save'] = 'saveRaw'
    compile_plan(alternative, task['features'], library())

    # Removing an unrelated suite must not rewrite the retained prompt messages.
    original = (PAPER / 'prompts.tex').read_text()
    public_original = original[original.index(r'\subsection{TodoMVC}'):]
    public = (PAPER / 'prompts_public.tex').read_text()
    pattern = r'\\begin\{lstlisting\}.*?\\end\{lstlisting\}'
    assert re.findall(pattern, public, re.S) == re.findall(pattern, public_original, re.S)

    report = {
        'all_passed': True,
        'manuscript_sources_sha256': sources,
        'data_sources_sha256': data_sources,
        'included_table_count': len(tables),
        'excluded_table_labels_absent': sorted(excluded),
        'matched_feedback_constant_endpoints_retained_in_prose': feedback,
        'bounded_search_outcomes_retained_in_prose': search_rows,
        'public_suite_cost': {
            'included_studies': [row['study'] for row in public_rows],
            'settled_microusd': public_cost, 'displayed_usd': '11.95',
        },
        'public_example': {'task': task['id'], 'plan': plan, 'diagnostic': diagnostic,
                           'alternative_save_binding_compiles': True},
        'retained_prompt_listing_bytes_match': True,
        'scope': ('Editorial scope and selected claims only. Table cells and PDF layout have separate reports. '
                  'No new model outputs, API calls, writable ledgers or benchmark browser scores. '
                  'Historical synthetic studies remain in the repository but are not manuscript evidence. '
                  'Does not establish independent human review, complete test coverage or an acceptance score.'),
    }
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n')
    print(json.dumps({key: report[key] for key in
                      ('all_passed', 'included_table_count', 'retained_prompt_listing_bytes_match')}))


if __name__ == '__main__':
    main()
