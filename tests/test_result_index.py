import json
import re

from studies import lookup, paper_performance as paper, result_index
from studies.study_io import ROOT


def test_displayed_scores_and_statuses_match_the_paper_and_link_to_the_matrix():
    source = (ROOT / lookup.MATRIX).read_text()
    matrix = json.loads(source)
    lines = source.splitlines()
    assert set(result_index.PROJECTS) == {
        dataset for dataset in lookup.DATASETS if not dataset.startswith("webgen-bench/")
    }
    result_index.sync()
    for dataset, (slug, _) in result_index.PROJECTS.items():
        path = ROOT / "paper-results" / (slug + ".md")
        page = path.read_text()
        project = lookup.DATASETS[dataset]
        models = paper.table_models(matrix, project)
        score_rows = [line for line in page.split("<details>")[0].splitlines() if "#L" in line]
        for model, row in zip(models, score_rows, strict=True):
            fields = [field.strip() for field in row.strip("|").split("|")]
            assert fields[0] == lookup.MODEL_NAMES[model]
            tex = paper.project_cells(matrix[model], project)
            for method, printed, link in zip(paper.METHODS, tex, fields[1:], strict=True):
                match = re.fullmatch(r"\[([^\]]+)\]\(\.\./\.\./(.+)#L(\d+)\)", link)
                assert match and match[2] == str(lookup.MATRIX)
                target = lines[int(match[3]) - 1].strip().rstrip(",")
                if "/" in printed:
                    assert match[1] == re.search(r"\d+/\d+", printed)[0]
                    assert json.loads("{" + target + "}") == {method: int(match[1].split("/")[0])}
                elif printed == "":
                    assert match[1] == "建库失败" and target == '"excluded_build_arms": ['
                else:
                    assert "--" in printed and match[1] == "无数据"
        for link in re.findall(r"\]\(([^)]+)\)", page):
            assert (path.parent / link.partition("#")[0]).is_file(), (dataset, link)
