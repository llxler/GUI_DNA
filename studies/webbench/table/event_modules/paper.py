"""Join the table protocols and the matched Flash decoding control to the main matrix."""
from copy import deepcopy
from pathlib import Path

from studies import paper_component_followup as components
from studies.study_io import read

HERE = Path(__file__).resolve().parent
EVENTS = HERE / 'result.json'
RECOVERED = HERE / 'source-recovery-result.json'
FOCUSED = HERE / 'focused-result.json'
PROFILES = HERE.parents[1] / 'table_interactions/result.json'
FLASH = HERE.parents[1] / 'form/flash_self_build/visible_targets/result.json'
FLASH_SCHEMA = FLASH.parent / 'schema-transfer-result.json'


def table_trials():
    for cell in read(PROFILES)['cells']:
        observations = components.outcomes(cell['rows'], 'gpt5-library')
        yield cell['model'], 'gpt5-library', 'profiles', PROFILES, observations
    for source in (EVENTS, RECOVERED, FOCUSED):
        for cell in read(source)['cases']:
            if cell['status'] == 'valid':
                observations = components.outcomes(cell['rows'], 'planned')
                yield cell['model'], 'self', 'handlers', source, observations


def attach(matrix):
    for model, arm, stage, source, observed in table_trials():
        entry = matrix[model]
        original = entry.get('extended_targets', {}).get('table') or entry['component_followup']['table']
        targets = original['targets']
        if not all(observed.get(n) is not None for n in targets):
            continue
        current = entry.setdefault('table_protocol_followup', deepcopy(original))
        current['passed'][arm] = sum(observed[n] for n in targets)
        current.setdefault('markers', {})[arm] = stage
        current['excluded_build_arms'] = [a for a in current.get('excluded_build_arms', []) if a != arm]
        current.setdefault('implementation_sources', {})[arm] = str(source.relative_to(components.ROOT))
    entry = matrix[components.FLASH]
    targets = entry['panel_a_self']['form']['targets']
    assert targets == list(range(1, 21))
    rows = read(FLASH)['rows']
    labels = {'direct': 'direct', 'human': 'human', 'gpt5-library': 'gpt5-library', 'self': 'file-a'}
    arms = {name: components.outcomes(rows, recorded) for name, recorded in labels.items()}
    assert all(set(values) == set(targets) for values in arms.values())
    if all(values[n] is not None for values in arms.values() for n in targets):
        entry['form_visible_targets'] = dict(
            n=len(targets), targets=targets, passed={k: sum(v.values()) for k, v in arms.items()},
            markers={k: 'flash-visible' for k in arms}, source=str(FLASH.relative_to(components.ROOT)),
        )
        followup = read(FLASH_SCHEMA)['cell']
        selected = components.outcomes(followup['rows'], 'gpt5-library')
        if all(selected.get(n) is not None for n in targets):
            entry['form_visible_targets']['passed']['gpt5-library'] = sum(selected[n] for n in targets)
            entry['form_visible_targets']['markers']['gpt5-library'] = 'flash-schema'
            entry['form_visible_targets']['schema_source'] = str(FLASH_SCHEMA.relative_to(components.ROOT))
    return matrix
