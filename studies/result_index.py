"""Build the browsable Table 1 project pages from the published matrix."""

import argparse
import json
import re

from studies import lookup
from studies.paper_performance import METHODS, table_models
from studies.study_io import ROOT


# Table 1 project pages use stable paths across protocol revisions.
PROJECTS = {
    "web-bench/table": ("A/table-editor", "表格编辑器 · Table editor"),
    "web-bench/svg-chart": ("A/svg-charts", "SVG 图表 · SVG charts"),
    "web-bench/form": ("A/question-form", "问卷 · Question form"),
    "web-bench/dom1": ("A/file-explorer", "文件管理器 · File explorer"),
    "web-bench/calculator": ("A/calculator", "计算器 · Calculator"),
    "todomvc": ("B/todomvc", "TodoMVC"),
    "webapp1k-duo": ("B/webapp1k-duo", "WebApp1K-Duo"),
    "webgen-bench": ("C/webgen-bench", "WebGen-Bench"),
}
UNITS = {
    "A": "每个目标是一项 Web-Bench 任务。候选页面通过该任务文件的全部官方断言计 1。",
    "todomvc": "每个目标是一组待办功能。候选实现通过该组测试计 1。",
    "webapp1k-duo": "每个目标是一对业务功能。该组合的四个测试用例全部通过计 1。",
    "webgen-bench": "每个目标是一项网站操作。浏览器判定完整完成计 1，部分完成计 0。",
}


def matrix_lines(source):
    """Index named object members in the matrix written with json.dumps(indent=2)."""
    lines = {}
    ancestors = []
    for number, line in enumerate(source.splitlines(), 1):
        key = re.match(r'^( +)("(?:[^"\\]|\\.)*"): ', line)
        if key:
            depth = len(key[1]) // 2 - 1
            if depth > len(ancestors):  # unnamed objects inside arrays
                continue
            ancestors[depth:] = [json.loads(key[2])]
            lines[tuple(ancestors)] = number
    return lines


def score_link(cell, lines):
    key = tuple(cell["row_keys"])
    if cell["status"] == "measured":
        label = f"{cell['score']}/{cell['denominator']}"
        key += ("passed", cell["method"])
    elif cell["status"] == "build_failed":
        label = "建库失败"
        key += ("excluded_build_arms",)
    else:
        label = "无数据"
    return f"[{label}](../../{lookup.MATRIX}#L{lines[key]})"


def evidence_links(cell):
    links = []
    if record := cell.get("method_record"):
        links.append(("实验记录", record))
    elif record := cell.get("row_source"):
        links.append(("该行汇总", record))
    if extra := cell.get("additional_targets_record"):
        links.append(("补测", extra))
    links.extend(("补判", path) for path in cell.get("supplemental_records", []))
    return " · ".join(f"[{label}](../../{path})" for label, path in links) or "见上表矩阵"


def render_project(matrix, lines, dataset):
    slug, title = PROJECTS[dataset]
    panel = slug.split("/")[0]
    project = lookup.DATASETS[dataset]
    models = table_models(matrix, project)
    header = "| 目标生成模型 | " + " | ".join(METHODS.values()) + " |"
    scores = [header, "| --- | ---: | ---: | ---: | ---: |"]
    records = [header, "| --- | --- | --- | --- | --- |"]
    for model in models:
        name = lookup.MODEL_NAMES[model]
        cells = [lookup.find_cell(matrix, dataset, model, method) for method in METHODS]
        scores.append(f"| {name} | " + " | ".join(score_link(cell, lines) for cell in cells) + " |")
        records.append(f"| {name} | " + " | ".join(evidence_links(cell) for cell in cells) + " |")
    example = models[0]
    return "\n".join([
        f"# {title}", "",
        f"[Table 1](../../README.md#按数据集模型和方法查-table-1) / {panel} / `{dataset}`", "",
        UNITS["A" if panel == "A" else dataset] + "分母是该模型四种方法共用的目标数。", "",
        *scores, "",
        "点击成绩可定位到主表 JSON 的对应行。建库失败对应论文空白格，无数据对应横线。", "",
        "<details>", "<summary>查看各模型、各方法的来源记录</summary>", "",
        *records, "", "</details>", "",
        "在仓库根目录可查询单格的矩阵键、来源文件及适用的筛选条件。例如", "",
        "```bash", f'python -m studies.lookup {dataset} "{lookup.MODEL_NAMES[example]}" Self', "```", "",
    ])


def sync(write=False, root=ROOT):
    source = (root / lookup.MATRIX).read_text()
    matrix = json.loads(source)
    lines = matrix_lines(source)
    for dataset, (slug, _) in PROJECTS.items():
        path = root / "paper-results" / (slug + ".md")
        content = render_project(matrix, lines, dataset)
        if write:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(content)
        elif not path.is_file() or path.read_text() != content:
            raise ValueError(f"Stale Table 1 index: {path.relative_to(root)}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--write", action="store_true")
    sync(write=parser.parse_args().write)
    print(f"Table 1: {len(PROJECTS)} project pages verified.")
