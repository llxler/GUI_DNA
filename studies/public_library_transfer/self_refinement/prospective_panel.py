"""Recompute the prospective two-build table from the original per-target verdicts."""
from pathlib import Path

from studies.public_library_transfer.self_replication import paper as historical
from studies.study_io import ROOT, dump, read, sha
from .svg_renderers.report import normalize

HERE = Path(__file__).resolve().parent
DUO = HERE / "duo_components/result.json"
COMPACT = DUO.parent / "compact/result.json"
TODO = HERE / "todomvc/verified_controller/result.json"
SCOPED_TODO = TODO.parent / "switch_scope/result.json"
SVG = HERE / "svg_renderers/result.json"
LINKED_SVG = SVG.parent / "module_linking/result.json"
PATCHED_SVG = SVG.parent / "runtime_patch/result.json"
DELIVERED_SVG = SVG.parent / "source_delivery/result.json"
TOKEN_SVG = SVG.parent / "dom_tokens/result.json"
FORM = HERE / "form_components/result.json"
FORM_WHITESPACE = FORM.parent / "whitespace/result.json"
SOURCES = (DUO, COMPACT, TODO, SCOPED_TODO, SVG, LINKED_SVG, PATCHED_SVG, DELIVERED_SVG, TOKEN_SVG,
           SVG.parent / "report.json", FORM, FORM_WHITESPACE)
LABELS = {"openai/gpt-oss-120b": "GPT-OSS-120B", "qwen/qwen3.5-9b": "Qwen3.5-9B"}
OUTPUT = ROOT / "studies/results/prospective-domain-builds-20261124.json"


def paired_rows(project, model, protocol, direct, replicas):
    """Compare on target identities and split rows when the builds have different coverage."""
    sets = {}
    assert set(replicas) == {"a", "b"}
    for rep, (plan, fixed) in replicas.items():
        assert set(plan) == set(fixed) == set(direct)
        assert all(value is None or type(value) is bool for arm in (plan, fixed, direct) for value in arm.values())
        sets[rep] = sorted(t for t in direct if all(x[t] is not None for x in (plan, fixed, direct)))

    def group(keys):
        tasks = sets[keys[0]]
        passed = {"direct": [t for t in tasks if direct[t]]}
        for k in keys:
            plan, fixed = replicas[k]
            passed["self_" + k] = [t for t in tasks if plan[t]]
            passed["fixed_" + k] = [t for t in tasks if fixed[t]]
        return {"project": project, "target_generator": model, "builder": "Self",
                "decoding": protocol, "libraries": list(keys), "scheduled": len(direct),
                "targets": tasks, "passed": {k: len(v) for k, v in passed.items()}, "passed_targets": passed}
    return [group(("a", "b"))] if sets["a"] == sets["b"] else [group((rep,)) for rep in ("a", "b")]


def outcomes(rows, **conditions):
    result = {}
    for row in rows:
        if all(row[k] == v for k, v in conditions.items()):
            assert row["task"] not in result
            result[row["task"]] = row["passed"]
    return result


def duo_rows(source, protocol):
    groups = []
    for model, data in read(source)["groups"].items():
        reps, direct = {}, None
        for rep in ("a", "b"):
            rows = data["repeats"]["build-" + rep]["rows"]
            columns = {k: {r["task"]: r["arms"][k]["passed"] for r in rows} for k in ("self", "fixed", "direct_repaired")}
            assert len(rows) == len(columns["direct_repaired"]) == 10
            if direct is None:
                direct = columns["direct_repaired"]
            assert columns["direct_repaired"] == direct
            reps[rep] = columns["self"], columns["fixed"]
        groups.extend(paired_rows("Duo", LABELS[model], protocol, direct, reps))
    return groups


def form_rows(source, protocol):
    data = read(source)
    assert data['model'] == 'openai/gpt-oss-120b'
    replicas = data['projects']['form']['replicas']
    direct = None
    groups = {}
    for key in ('a', 'b'):
        rows = replicas['build-' + key]['rows']
        assert len(rows) == 20 and {r['task'] for r in rows} == set(range(1, 21))
        columns = {k: {r['task']: r[k]['passed'] for r in rows} for k in ('self', 'fixed', 'direct')}
        if direct is None:
            direct = columns['direct']
        assert columns['direct'] == direct
        groups[key] = columns['self'], columns['fixed']
    return paired_rows('Question form', 'GPT-OSS-120B', protocol, direct, groups)


def todo_rows(source, protocol):
    todo = read(source)["rows"]
    direct = outcomes(todo, group="direct", stage="final", arm="direct")
    reps = {g: tuple(outcomes(todo, group=g.upper(), stage="final", arm=arm)
                     for arm in ("planned", "fixed")) for g in ("a", "b")}
    assert set(direct) == {f'todo-{i:02d}' for i in range(1, 9)} and len(todo) == 80
    return paired_rows("TodoMVC", "Gemma 3 12B", protocol, direct, reps)


def svg_rows(source, protocol, direct_source=None, direct_arm='final'):
    scores = [{**r, "passed": normalize(r)[0]} for r in read(source)["rows"]]
    direct_scores = scores
    if direct_source is not None:
        relaxed = read(direct_source)
        assert not relaxed['newly_accepted_library_attempts']
        direct_scores = [{**r, "passed": normalize(r)[0]} for r in relaxed['rows']]
    direct = outcomes(direct_scores, group="direct", arm=direct_arm)
    assert set(direct) == set(range(1, 21))
    reps = {g: tuple(outcomes(scores, group=g.upper(), arm=arm)
                     for arm in ("planned", "fixed")) for g in ("a", "b")}
    return paired_rows("SVG charts", "Qwen3-Coder-30B", protocol, direct, reps)


def rows():
    result = duo_rows(DUO, "Components") + duo_rows(COMPACT, "Compact UI")
    result += todo_rows(TODO, "Verified keys") + todo_rows(SCOPED_TODO, "Case scopes")
    result += svg_rows(SVG, 'Renderers') + svg_rows(SVG, 'Relaxed files', direct_source=DELIVERED_SVG)
    result += svg_rows(LINKED_SVG, 'Module links') + svg_rows(PATCHED_SVG, 'Error repair')
    result += svg_rows(TOKEN_SVG, 'DOM tokens', direct_arm='delivery')
    return result + form_rows(FORM, 'Question types') + form_rows(FORM_WHITESPACE, 'JSON spaces')


def row_sources(row):
    protocols = {"Components": (DUO,), "Compact UI": (COMPACT,), "Verified keys": (TODO,),
                 "Case scopes": (TODO, SCOPED_TODO), "Renderers": (SVG,), "Module links": (SVG, LINKED_SVG),
                 "Error repair": (LINKED_SVG, PATCHED_SVG), "Relaxed files": (SVG, DELIVERED_SVG),
                 "DOM tokens": (PATCHED_SVG, DELIVERED_SVG, TOKEN_SVG),
                 "Question types": (FORM,), "JSON spaces": (FORM, FORM_WHITESPACE)}
    if row['decoding'] in protocols:
        return protocols[row['decoding']]
    if row['builder'] == 'GPT-6 Astra':
        return (historical.NATIVE, historical.STRONG/'result.json', historical.STRONG/'native/result.json')
    if row['project'] == 'TodoMVC':
        return (historical.TODOMVC,)
    if row['target_generator'] == 'Qwen3-Coder-30B':
        return (historical.CODER,)
    assert row['builder'] == 'Self' and row['target_generator'] == 'Qwen3.5-9B'
    return historical.LINKED, historical.NATIVE


def evidence():
    from studies.paper_performance import order_build_rows
    all_rows = []
    for row in order_build_rows([*historical.rows(), *rows()]):
        source_paths = [str(p.relative_to(ROOT)) for p in row_sources(row)]
        all_rows.append({**row, 'n': len(row['targets']), 'sources': source_paths})
    direct_rules = {'Components': 'First public-component protocol, including its allowed direct public repair.',
                    'Compact UI': 'New direct answers under the same compact public UI specification and repair rule.',
                    'Verified keys': 'Direct after one eligible public-controller repair, under the shared JavaScript parser.',
                    'Case scopes': 'The same received sources, open to the same scope-safe switch syntax correction.',
                    'Renderers': 'Direct with its public rendering repair and original file-delivery rule.',
                    'Relaxed files': 'The original rendering libraries versus the direct source recovered from the same replies.',
                    'Module links': 'The same direct endpoints after the shared module-link rule.',
                    'Error repair': 'Direct after the shared public runtime feedback stage.',
                    'DOM tokens': 'Recovered direct-file delivery with the same error-witnessed DOM token correction.',
                    'Question types': 'Direct under the public questionnaire host and eligible public repair.',
                    'JSON spaces': 'The same sources with formatting escapes outside quoted JSON strings normalized for both arms.'}
    return {'scope': 'Table 1 Panel D. Each row uses its named protocol and the common target identities listed. '
                     'Counts include observed delivery failures. Unobserved endpoints are excluded. '
                     'Each paired deployment variant retains its own direct acceptance and repair rules.',
            'direct_rules_for_new_protocols': direct_rules,
            'source_sha256': {str(p.relative_to(ROOT)): sha(p) for p in (*SOURCES, *historical.SOURCES)},
            'rows': all_rows}


def verify_or_publish(write=False):
    facts = evidence()
    if write:
        dump(OUTPUT, facts)
    assert read(OUTPUT) == facts


if __name__ == '__main__':
    verify_or_publish()
