"""Export the prompts of every suite and method to a LaTeX appendix (zero API).

    uv run python -m test.export_prompts                 # writes DNA_latex/prompts.tex (local paper dir)
    uv run python -m test.export_prompts --out some.tex

The messages are produced by the same functions the runs call (`messages_for`, `free_messages`, the Duo templates),
on one representative task per suite.  Long, mechanically generated blocks (frozen library listings, the current
index.html of the sequential Web-Bench protocol) are replaced by a bracketed marker that states what was there and how
long it was; everything else is verbatim.  Non-ASCII characters are mapped to ASCII for pdflatex `listings`
(the mapping is printed).  Also exported: the repair-feedback templates of every runner.
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUT = ROOT / 'DNA_latex' / 'prompts.tex'
ASCII_MAP = {'\u2014': '--', '\u2013': '-', '\u2192': '->', '\u2026': '...', '\u201c': '"', '\u201d': '"', '\u2018': "'", '\u2019': "'",
             '\u203a': '>', '\u2039': '<', '\u00a0': ' ', '\u2264': '<=', '\u2265': '>=', '\u00d7': 'x', '\u2022': '*', '\u2502': '|'}


def ascii_only(text, seen):
    out = []
    for ch in text:
        if ord(ch) < 128:
            out.append(ch)
        elif ch in ASCII_MAP:
            seen[ch] = seen.get(ch, 0) + 1
            out.append(ASCII_MAP[ch])
        else:
            seen[ch] = seen.get(ch, 0) + 1
            out.append('?')
    return ''.join(out)


def marker(what, text):
    return f'[[{what}: {len(text):,} characters, {text.count(chr(10)) + 1} lines; omitted here]]'


def head_of(listing, n):
    """First n entries of a '- `sig` ...' listing (entries start with '- `' at line start)."""
    lines = listing.split('\n')
    starts = [i for i, l in enumerate(lines) if l.startswith('- `')]
    end = starts[n] if len(starts) > n else len(lines)
    return '\n'.join(lines[:end]).rstrip()


def block(title, messages, notes=''):
    parts = [f'\\paragraph{{{title}}}' + (f' {notes}' if notes else '')]
    for m in messages:
        parts.append(f'\\textit{{{m["role"]}:}}')
        parts.append('\\begin{lstlisting}[style=prompt]')
        parts.append(m['content'])
        parts.append('\\end{lstlisting}')
    return '\n'.join(parts)


def tex_escape(text):
    return text.replace('\\', '\\textbackslash{}').replace('_', '\\_').replace('&', '\\&').replace('%', '\\%').replace('#', '\\#').replace('{', '\\{').replace('}', '\\}')


def list16():
    from experiments.scale_study import domain
    task = domain.tasks()[0]
    lib = domain.library()
    out = [f'\\subsection{{\\listsuite}}\n\\label{{app:prompts-list16}}\nRepresentative task: \\code{{{task["id"]}}} (features {", ".join(task["features"])}). '
           'The user message is one JSON object with the fields \\code{requirement}, \\code{features}, \\code{initial} and \\code{functions}; '
           'the three preloaded methods (\\free, \\method, \\nocheck) receive byte-identical user messages (functions without bodies), '
           '\\freelib receives the same list with a \\code{code} field per function. Only the system message differs between methods.']
    names = {'plan_checked': '\\method and \\nocheck (identical prompt; the compiler differs)', 'linked_js': '\\free (glue code over the preloaded library)',
             'dna': '\\freelib (function bodies in the prompt, model writes functions and glue)'}
    for method in ['plan_checked', 'linked_js', 'dna']:
        msgs = domain.messages_for(task, method, lib)
        functions = [{k: v for k, v in f.items() if k != 'code' or method == 'dna'} for f in lib['functions']]
        dumped = json.dumps(functions, ensure_ascii=False)
        user = msgs[1]['content']
        assert dumped in user
        example = json.dumps(functions[0], ensure_ascii=False)
        user = user.replace(dumped, f'[{example}, {marker(f"{len(functions) - 1} more function entries of the same form", dumped[len(example) + 2:-1])}]')
        out.append(block(names[method], [msgs[0], {'role': 'user', 'content': user}]))
    repair = ('Repair using only the public feedback below. Preserve the requested output schema and return the complete candidate.\n'
              '{"passed": false, "compile_error": "<compiler diagnostic>"}   or   {"passed": false, "error": ..., <public case results>}')
    out.append(block('Repair message (all methods)', [{'role': 'user', 'content': repair}],
                     'The public feedback object is the compiler diagnostic or the public-case results; hidden cases never appear.'))
    return '\n\n'.join(out)


def todomvc():
    from test.todomvc_dna import domain
    from test.todomvc_dna.library import library
    lib = library()
    task = next(t for t in domain.tasks() if t['id'] == 'todo-08')
    listing = domain.library_listing(lib, task['features'])
    short = head_of(listing, 2) + '\n' + marker(f'{len(lib["functions"]) - 2} more atoms in the same form (signature, feature, description, frozen source)', listing[len(head_of(listing, 2)):])
    out = [f'\\subsection{{TodoMVC}}\n\\label{{app:prompts-todomvc}}\nRepresentative task: \\code{{{task["id"]}}} (features {", ".join(task["features"])}, all 24 official tests). '
           'The requirement text is the Functionality section of the TodoMVC specification restricted to the enabled features. '
           '\\method and \\nocheck receive the identical prompt; \\freelib receives the \\free prompt plus the frozen library listing that the plan prompt shows.']
    names = {'dna': '\\method and \\nocheck', 'free': '\\free', 'free_lib': '\\freelib'}
    for method in ['dna', 'free', 'free_lib']:
        msgs = domain.messages_for(task, method, lib)
        user = msgs[1]['content']
        if listing in user:
            user = user.replace(listing, short)
        out.append(block(names[method], [msgs[0], {'role': 'user', 'content': user}]))
    repair = ('The plan was rejected by the compiler:\n<diagnostic>\nReturn a corrected plan as JSON only.\n'
              '--- or ---\nPublic smoke check failed:\n- <problem>\n- <problem>\nReturn a corrected plan as JSON only.\n'
              '--- free-form methods ---\nYour output could not be used:\n<parse error>\nReturn a corrected complete JavaScript source as JSON only.')
    out.append(block('Repair messages', [{'role': 'user', 'content': repair}],
                     'The public smoke check reports page errors and whether one added todo appears in the list and in localStorage; the official tests are never shown.'))
    return '\n\n'.join(out)


def webbench():
    from test.webbench_dna import domain
    from test.webbench_dna.library import library
    lib = library()
    task = next(t for t in domain.tasks() if t['id'] == 'task-5')
    init_html = (domain.HERE / 'harness' / 'src-init.index.html').read_text()
    listing = domain.library_listing(lib)
    short = head_of(listing, 2) + '\n' + marker(f'{len(lib["functions"]) - 2} more atoms in the same form', listing[len(head_of(listing, 2)):])
    out = [f'\\subsection{{\\webbench}}\n\\label{{app:prompts-webbench}}\nRepresentative task: \\code{{{task["id"]}}} ({task["level"]}; features {", ".join(task["features"])}). '
           'The plan prompt lists the official descriptions of tasks $1..k$ verbatim; the free-form prompt follows the benchmark protocol and shows the '
           'current \\code{index.html} (the official initial page at task 1, the model\'s own previous output afterwards) with the description of task $k$ only. '
           '\\method and \\nocheck receive the identical prompt.']
    msgs = domain.messages_for(task, 'dna', lib)
    user = msgs[1]['content']
    assert listing in user
    out.append(block('\\method and \\nocheck', [msgs[0], {'role': 'user', 'content': user.replace(listing, short)}]))
    msgs = domain.free_messages(task, init_html, None)
    user = msgs[1]['content'].replace(init_html, marker('current index.html (official src-init page at task 1)', init_html))
    out.append(block('\\free', [msgs[0], {'role': 'user', 'content': user}]))
    msgs = domain.free_messages(task, init_html, lib)
    user = msgs[1]['content'].replace(init_html, marker('current index.html', init_html))
    lib_block = '\n'.join(f"- `{f['signature']}` — {f['description']}\n  ```js\n  {f['code']}\n  ```" for f in lib['functions'])
    assert lib_block in user
    user = user.replace(lib_block, head_of(lib_block, 1) + '\n' + marker(f'{len(lib["functions"]) - 1} more functions with their frozen source', lib_block[len(head_of(lib_block, 1)):]))
    out.append(block('\\freelib', [msgs[0], {'role': 'user', 'content': user}]))
    repair = ('The plan was rejected by the compiler:\n<diagnostic>\nReturn a corrected plan as JSON only.\n'
              '--- or ---\nPublic smoke check failed:\n- <problem>\nReturn a corrected plan as JSON only.\n'
              '--- free-form methods ---\nYour output could not be used:\n<parse error>\nReturn a corrected complete index.html as JSON only.')
    out.append(block('Repair messages', [{'role': 'user', 'content': repair}],
                     'The public check reports page and console errors and whether the tool buttons are clickable; the official specs are never shown.'))
    return '\n\n'.join(out)


def duo():
    from experiments.webapp1k_probe import SYSTEM, PROMPT
    from test.webapp1k_dna.run import DNA_SYSTEM, DNA_USER
    out = ['\\subsection{\\duo}\n\\label{app:prompts-duo}\nThe user message of \\free is the official WebApp1K prompt with the concatenated Duo test file in place of '
           '\\code{\\{tests\\}}; the plan prompt shows the same test file and the frozen atom library of the task (variant id, source, whether the variant passed its own public tests).']
    out.append(block('\\free (official prompt)', [{'role': 'system', 'content': SYSTEM}, {'role': 'user', 'content': PROMPT}]))
    out.append(block('\\method', [{'role': 'system', 'content': DNA_SYSTEM}, {'role': 'user', 'content': DNA_USER}]))
    repair = ('The plan was rejected by the compiler:\n<diagnostic>\nReturn a corrected plan as JSON only.\n'
              '--- or ---\n<k>/<n> tests passed. Failing tests:\n- <test title>: <assertion message>\nReturn a corrected plan as JSON only.   (free: Return the corrected full module as JSON only.)')
    out.append(block('Repair messages', [{'role': 'user', 'content': repair}], 'Public Jest feedback is the task\'s own test file, which is the prompt in this benchmark.'))
    return '\n\n'.join(out)


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--out', type=Path, default=DEFAULT_OUT)
    args = parser.parse_args()
    seen = {}
    body = '\n\n'.join([list16(), todomvc(), webbench(), duo()])
    body = ascii_only(body, seen)
    assert '\\end{lstlisting}' not in body.replace('\\end{lstlisting}', '', body.count('\\begin{lstlisting}'))
    header = (f'% Generated by test/export_prompts.py on {time.strftime("%Y-%m-%d")} from the live prompt builders; do not edit by hand.\n'
              f'% Non-ASCII characters mapped to ASCII: {json.dumps({k: v for k, v in seen.items()}, ensure_ascii=False)}\n')
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(header + body + '\n')
    print(f'wrote {args.out} ({len(body):,} chars); non-ASCII replaced: {seen}', file=sys.stderr)


if __name__ == '__main__':
    main()
