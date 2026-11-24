"""Split literal file headings, then link only unambiguous named ES module imports."""

from collections import defaultdict
import posixpath
import re
import subprocess

NAME = r"[A-Za-z_$][\w$]*"
PATH = r"(?:[A-Za-z0-9_-]+/)*[A-Za-z0-9_.-]+\.(?:js|mjs|css)"
HEADING = re.compile(rf"(?://\s*({PATH})\s*|/\*\s*({PATH})\s*\*/)")
ENTRY = re.compile(r"//\s*main entry point\s*", re.I)
FENCE = re.compile(r"```(?:js|javascript|mjs|css)?", re.I)
DEFINITION = re.compile(rf"^export\s+(?:async\s+)?(?:class|function|let|const|var)\s+({NAME})\b", re.M)
LISTED = re.compile(r"^export\s*\{([^{}\n]+)\}", re.M)
STAR = re.compile(r"""^export\s*\*\s*from\s*['"](\.[^'"]+)['"]""", re.M)
IMPORT = re.compile(r"""^([ \t]*)import\s*\{([^{}\n]*)\}\s*from\s*(['"])(\.[^'"]+)\3[ \t]*;?[ \t]*$""", re.M)
BINDING = re.compile(rf"^({NAME})(?:\s+as\s+({NAME}))?$")


def line_path(s, entry):
    if ENTRY.fullmatch(s):
        return entry
    found = HEADING.fullmatch(s)
    return (found[1] or found[2]) if found else None


def split(program, spec):
    lines = program.splitlines(keepends=True)
    names = [line_path(line.rstrip("\r\n"), spec["entry"]) for line in lines]
    fences = {i for i, line in enumerate(lines) if FENCE.fullmatch(line.rstrip("\r\n"))}
    def adjacent_boundary(i, step):
        j = i + step
        while 0 <= j < len(lines) and (j in fences or not lines[j].strip()):
            j += step
        return not 0 <= j < len(lines) or names[j] is not None
    chunks, active, stripped = {}, None, []
    for i, line in enumerate(lines):
        if i in fences and (adjacent_boundary(i, 1) or adjacent_boundary(i, -1)):
            stripped.append(i + 1)
            continue
        if names[i]:
            active = names[i]
            if active not in spec["files"] or active in chunks:
                raise ValueError(f"Unexpected or repeated module heading: {active}")
            chunks[active] = []
        if active:
            chunks[active].append(line)
        elif line.strip():
            raise ValueError("Unlabelled program before the first module")
    return {name: "".join(body) for name, body in chunks.items()}, stripped


def resolve(name, rel):
    return posixpath.normpath(posixpath.join(posixpath.dirname(name), rel))


def link_named(files):
    definitions = {p: set(DEFINITION.findall(v)) for p, v in files.items()}
    owners = defaultdict(set)
    available = {p: set(ds) for p, ds in definitions.items()}
    stars = {p: [resolve(p, s) for s in STAR.findall(v)] for p, v in files.items()}
    for p, names in definitions.items():
        for n in names:
            owners[n].add(p)
        for listed in LISTED.findall(files[p]):
            for chunk in listed.split(","):
                binding = BINDING.fullmatch(chunk.strip())
                if binding:
                    available[p].add(binding[2] or binding[1])
    for _ in available:
        for p, targets in stars.items():
            for target in targets:
                available[p].update(available.get(target, set()))
    linked, changes = {}, []
    for p, src in files.items():
        def rewrite(found):
            target = resolve(p, found[4])
            if target not in available:
                return found[0]
            grouped = defaultdict(list)
            for item in found[2].split(","):
                if not item.strip():
                    continue
                bind = BINDING.fullmatch(item.strip())
                if not bind:
                    return found[0]
                key = bind[1]
                choice = target
                if key not in available[target]:
                    candidates = owners[key] - {p}
                    if len(candidates) != 1:
                        raise ValueError(f"{p}: unresolved or ambiguous {key} from {target}")
                    choice, = candidates
                    changes.append({"importer": p, "symbol": key, "from": target, "to": choice})
                grouped[choice].append(item.strip())
            if not grouped or set(grouped) == {target}:
                return found[0]
            result = []
            for name, bindings in grouped.items():
                rel = posixpath.relpath(name, posixpath.dirname(p) or ".")
                if not rel.startswith("."):
                    rel = "./" + rel
                result.append(f"{found[1]}import {{ {', '.join(bindings)} }} from {found[3]}{rel}{found[3]};")
            return "\n".join(result)
        linked[p] = IMPORT.sub(rewrite, src)
    return linked, changes


def compile_sources(program, styles, spec):
    sections, fences = split(program, spec)
    if spec["entry"] not in sections:
        raise ValueError(f"No generated entry section for {spec['entry']}")
    scripts = {p: text for p, text in sections.items() if not p.endswith(".css")}
    linked, changes = link_named(scripts)
    for p, text in linked.items():
        checked = subprocess.run(["node", "--input-type=module", "--check", "-"], input=text,
                                 text=True, capture_output=True, timeout=15)
        if checked.returncode:
            raise ValueError(f"{p}: {checked.stderr[:500]}")
    audit = {"sections": list(sections), "removed_fence_lines": fences, "redirected_imports": changes,
             "stylesheet_sources": list(styles)}
    return linked | styles, audit
