"""Plan-checked composition of frozen WebApp1K atoms (the GUI-DNA method on an external benchmark).

A *plan* is the only thing the model writes:
    {"select": {"<atom>": "<variant>", ...},            # one frozen variant per atom of the Duo task
     "order": ["<atom>", ...],                          # layout order (permutation of the atoms)
     "relabel": [{"atom": "<atom>", "from": "<static string>", "to": "<new string>"}, ...]}

`compile_plan` validates the plan against the public test file and the frozen library and stitches a
wrapper module that mounts the selected atoms (props forwarded).  Atom logic is never edited: the only
permitted change is replacing visible static strings (JSX text / placeholder / aria-label / alt / title /
data-testid), which the compiler applies by splicing source ranges found with @babel/parser.

Static checks (the `checked=True` arm):
  * structural: known atoms, known variants, permutation, well-formed relabels;
  * a relabel may not break a string that the atom's own tests select (the new string must still satisfy every
    own selector that matched the old one);
  * cross-atom collision: no selector used by atom X's tests may match a static string of atom Y
    (the exact failure mode seen in the free-form baseline: duplicate `getByText(/Edit/i)` matches).
Dynamic strings (e.g. setMessage('Failed ...')) that match the other atom's selectors are reported as
warnings, not errors, because they only appear after that atom's own actions.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import subprocess
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
STAGING = ROOT / 'artifacts/benchmark-probe/WebApp1k/staging'
NODE_PATH = STAGING / 'node_modules'

QUERY = re.compile(
    r"(?:getBy|getAllBy|queryBy|queryAllBy|findBy|findAllBy)"
    r"(Text|LabelText|PlaceholderText|TestId|Role|DisplayValue|AltText|Title)\(\s*"
    r"(?:/((?:\\/|[^/])+)/([a-z]*)|'((?:\\'|[^'])*)'|\"((?:\\\"|[^\"])*)\")"
    r"(?:\s*,\s*\{[^}]*name\s*:\s*(?:/((?:\\/|[^/])+)/([a-z]*)|'((?:\\'|[^'])*)'|\"((?:\\\"|[^\"])*)\"))?")
KINDS = {  # which static-string kinds each query inspects (conservative over-approximation of RTL semantics)
    'Text': {'text', 'attr:value'}, 'LabelText': {'text', 'attr:aria-label', 'attr:label'},
    'PlaceholderText': {'attr:placeholder'}, 'TestId': {'attr:data-testid'},
    'Role': {'text', 'attr:aria-label', 'attr:value', 'attr:title'}, 'DisplayValue': {'attr:value'},
    'AltText': {'attr:alt'}, 'Title': {'attr:title'}}
DYNAMIC_KINDS = {'Text', 'LabelText', 'Role'}


def sha256(text):
    return hashlib.sha256(text.encode()).hexdigest()


class Selector:
    def __init__(self, query, pattern, flags, exact):
        self.query, self.exact = query, exact
        if exact is None:
            self.regex = re.compile(pattern, re.I if 'i' in flags else 0)
            self.label = f'{query}(/{pattern}/{flags})'
        else:
            self.regex = None
            self.label = f'{query}({json.dumps(exact)})'

    def matches(self, value):
        value = re.sub(r'\s+', ' ', value).strip()
        return bool(self.regex.search(value)) if self.regex else value == self.exact

    def __repr__(self):
        return self.label


def parse_selectors(test_source):
    out = []
    for m in QUERY.finditer(test_source):
        query = m.group(1)
        if query == 'Role':
            if m.group(6) is not None:
                out.append(Selector(query, m.group(6), m.group(7), None))
            elif m.group(8) is not None or m.group(9) is not None:
                out.append(Selector(query, None, '', m.group(8) if m.group(8) is not None else m.group(9)))
            continue  # role without a name constraint does not depend on text
        if m.group(2) is not None:
            out.append(Selector(query, m.group(2), m.group(3), None))
        else:
            out.append(Selector(query, None, '', m.group(4) if m.group(4) is not None else m.group(5)))
    return out


def selectors_by_atom(test_source, atoms):
    """Duo tests are two single-feature test files concatenated: first half -> first atom, second half -> second."""
    blocks = re.split(r'^(?:test|it)\(', test_source, flags=re.M)[1:]
    if len(atoms) == 2 and len(blocks) % 2 == 0:
        half = len(blocks) // 2
        parts = ['\n'.join(blocks[:half]), '\n'.join(blocks[half:])]
    else:  # unknown layout: every selector belongs to every atom (strictest reading)
        parts = [test_source] * len(atoms)
    return {atom: parse_selectors(part) for atom, part in zip(atoms, parts)}


def analyze(code, relabels=()):
    """Static strings, dynamic strings and relabelled source of one atom (via analyze.js)."""
    with tempfile.TemporaryDirectory() as tmp:
        src = Path(tmp) / 'atom.js'
        src.write_text(code)
        args = ['node', str(HERE / 'analyze.js'), str(src)]
        if relabels:
            edits = Path(tmp) / 'edits.json'
            edits.write_text(json.dumps(list(relabels)))
            args.append(str(edits))
        env = {**os.environ, 'NODE_PATH': str(NODE_PATH)}
        env.pop('OPENROUTER_API_KEY', None)
        done = subprocess.run(args, capture_output=True, text=True, env=env, timeout=60)
    if done.returncode != 0:
        raise ValueError('atom does not parse as a JSX module: ' + done.stderr.strip()[-600:])
    return json.loads(done.stdout)


def plan_template(duo, library):
    """Deterministic default plan: first variant of every atom, file-name order, no relabels (the rule control)."""
    return {'select': {a: library[a][0]['variant'] for a in duo['atoms']}, 'order': list(duo['atoms']), 'relabel': []}


def rule_plan(duo, library, prefer):
    """Rule control for one model: that model's own atoms when present, else the first variant."""
    select = {}
    for atom in duo['atoms']:
        own = [v for v in library[atom] if v.get('origin') == prefer]
        select[atom] = (own or library[atom])[0]['variant']
    return {'select': select, 'order': list(duo['atoms']), 'relabel': []}


def compile_plan(plan, duo, library, test_source, checked=True):
    """Validate the plan, apply relabels, check cross-atom selector collisions, stitch the wrapper.

    Returns {'files': {relative_path: source}, 'warnings': [...], 'texts': {...}}; raises ValueError with a
    message the model can act on.  Never looks at anything but the public test file and the frozen library.
    """
    atoms = list(duo['atoms'])
    if not isinstance(plan, dict):
        raise ValueError('plan must be a JSON object')
    select, order, relabel = plan.get('select'), plan.get('order'), plan.get('relabel', [])
    if not isinstance(select, dict) or not isinstance(order, list) or not isinstance(relabel, list):
        raise ValueError('required fields: "select" object, "order" array, "relabel" array')
    if set(select) != set(atoms):
        raise ValueError(f'"select" must have exactly these atoms: {atoms}')
    if sorted(order) != sorted(atoms) or len(order) != len(atoms):
        raise ValueError(f'"order" must be a permutation of {atoms}')
    chosen = {}
    for atom, variant in select.items():
        match = [v for v in library[atom] if v['variant'] == variant]
        if not match:
            raise ValueError(f'unknown variant {variant!r} for atom {atom}; available: {[v["variant"] for v in library[atom]]}')
        chosen[atom] = match[0]
    edits = {a: [] for a in atoms}
    for i, item in enumerate(relabel):
        if not isinstance(item, dict) or item.get('atom') not in atoms:
            raise ValueError(f'relabel[{i}] must be {{"atom": one of {atoms}, "from": string, "to": string}}')
        src, dst = item.get('from'), item.get('to')
        if not isinstance(src, str) or not isinstance(dst, str) or not src.strip() or not dst.strip():
            raise ValueError(f'relabel[{i}]: "from" and "to" must be non-empty strings')
        if src.strip() == dst.strip():
            raise ValueError(f'relabel[{i}]: "to" must differ from "from"')
        edits[item['atom']].append({'from': src, 'to': dst})
    selectors = selectors_by_atom(test_source, atoms)
    analyses, warnings = {}, []
    for atom in atoms:
        if checked:
            own = selectors[atom]
            for edit in edits[atom]:
                # A string the atom's own tests select may only change if every such selector still matches it.
                broken = [s for s in own if s.matches(edit['from']) and not s.matches(edit['to'])]
                if broken:
                    raise ValueError(f'relabel of {edit["from"]!r} to {edit["to"]!r} in atom {atom} is not allowed: '
                                     f'its own tests select it via {broken[0]}, which the new string no longer matches')
        analyses[atom] = analyze(chosen[atom]['code'], edits[atom])
        if analyses[atom]['missing']:
            raise ValueError(f'atom {atom} variant {chosen[atom]["variant"]} has no static string {analyses[atom]["missing"][0]!r}; '
                             f'static strings are: {[s["value"] for s in analyses[atom]["static"]]}')
    if checked:
        errors = []
        for atom in atoms:
            for other in atoms:
                if other == atom:
                    continue
                for sel in selectors[atom]:
                    kinds = KINDS[sel.query]
                    hits = [s for s in analyses[other]['static'] if s['kind'] in kinds and sel.matches(s['value'])]
                    for h in hits:
                        errors.append(f'{sel} used by the tests of {atom} also matches static {h["kind"]} {h["value"]!r} in atom {other} '
                                      f'(variant {chosen[other]["variant"]}); relabel it or select another variant')
                    if sel.query in DYNAMIC_KINDS:
                        for d in analyses[other]['dynamic']:
                            if sel.matches(d):
                                warnings.append(f'{sel} used by the tests of {atom} would also match the runtime string {d!r} of atom {other} if it is displayed')
        if errors:
            raise ValueError('cross-atom selector collision:\n- ' + '\n- '.join(errors))
    files = {}
    imports, mounts = [], []
    for i, atom in enumerate(order):
        rel = f'atoms/{atom}__{chosen[atom]["variant"]}.js'
        files[rel] = analyses[atom]['code']
        imports.append(f"import Atom{i} from './{rel[:-3]}';")
        mounts.append(f'      <section data-atom="{atom}"><Atom{i} {{...props}} /></section>')
    files[f'{duo["module"]}.js'] = ('import React from \'react\';\n' + '\n'.join(imports) + '\n\n'
                                    '// Generated wrapper: mounts frozen atoms in plan order and forwards every prop.\n'
                                    f'export default function {duo["module"]}(props) {{\n  return (\n    <div>\n'
                                    + '\n'.join(mounts) + '\n    </div>\n  );\n}\n')
    texts = {a: {'static': analyses[a]['static'], 'dynamic': analyses[a]['dynamic']} for a in atoms}
    return {'files': files, 'warnings': warnings, 'texts': texts,
            'selected': {a: {'variant': chosen[a]['variant'], 'sha256': chosen[a]['sha256']} for a in atoms}}


def library_prompt(duo, library):
    """Public description of the atoms available to this Duo task (sources included; origins hidden)."""
    lines = []
    for atom in duo['atoms']:
        lines.append(f'### atom `{atom}`')
        for v in library[atom]:
            ok = 'yes' if v.get('verified') else 'no'
            lines += [f'#### variant `{v["variant"]}` (passes its own public single-feature tests: {ok})', '```js', v['code'].rstrip(), '```']
    return '\n'.join(lines)
