"""Check the current local PDF against source freshness and publication format.

Run with: uv run --with pymupdf python -m test.paper_format
This checks build/format evidence, not scientific validity or human review.
"""
import hashlib
import argparse
import json
from pathlib import Path
import re

import pymupdf

ROOT = Path(__file__).resolve().parents[1]
PAPER = ROOT / 'DNA_latex'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def expand(text):
    return re.sub(r'\\input\{([^}]+)\}',
                  lambda m: expand((PAPER / (m.group(1) + '.tex')).read_text()), text)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--report', type=Path, default=ROOT / 'test/results/paper-format-20261115.json')
    args = parser.parse_args()
    pdf = PAPER / 'main.pdf'
    doc = pymupdf.open(pdf)
    main_source = (PAPER / 'main.tex').read_text().split(r'\appendix')[0]
    main_text = expand(main_source)
    table_count = len(re.findall(r'\\begin\{table\*?\}', main_text))
    figure_count = len(re.findall(r'\\begin\{figure\*?\}', main_text))
    pages = [p.get_text() for p in doc]
    conclusion = [i + 1 for i, text in enumerate(pages) if re.search(r'^\d+\. Conclusion\s*$', text, re.M)]
    impact = [i + 1 for i, text in enumerate(pages) if re.search(r'^Impact Statement\s*$', text, re.M)]
    assert len(conclusion) == len(impact) == 1
    conclusion_source = main_text.split(r'\section{Conclusion}', 1)[1].split(r'\section*{Impact Statement}', 1)[0]
    conclusion_source = re.sub(r'%[^\n]*|\\label\{[^}]+\}', '', conclusion_source)
    ending = ' '.join(conclusion_source.split()[-12:])
    assert '\\' not in ending, 'Update the conclusion-ending check for new LaTeX commands'
    ending_pages = [i + 1 for i, text in enumerate(pages)
                    if ending in ' '.join(text.replace('-\n', '').split())]
    assert len(ending_pages) == 1, 'Locate the end, not just the heading, of the main text'
    float_pages = {}
    for kind, count in [('Table', table_count), ('Figure', figure_count)]:
        for number in range(1, count + 1):
            matches = [i + 1 for i, text in enumerate(pages)
                       if re.search(r'^' + kind + r'\s+' + str(number) + r'\.', text, re.M)]
            assert matches, (kind, number)
            float_pages[f'{kind} {number}'] = min(matches)
    last_main = max([ending_pages[0], *float_pages.values()])
    assert last_main <= 8 and impact[0] >= conclusion[0]
    fonts = {font[0]: font for p in doc for font in p.get_fonts()}
    font_types = sorted({f[2] for f in fonts.values()})
    embedded = all(bool(doc.extract_font(xref)[3]) for xref in fonts)
    assert font_types == ['Type1'] and embedded
    assert doc.metadata['author'] == 'Anonymous Authors'
    log = (ROOT / 'artifacts/paper-build/build/main.log').read_text()
    undefined = len(re.findall(r'(?:Reference|Citation) .+? undefined|There were undefined references', log))
    overfull = len(re.findall(r'Overfull \\[hv]box', log))
    assert undefined == overfull == 0
    sources = [p for p in PAPER.iterdir() if p.suffix in ('.tex', '.bib', '.sty', '.bst')]
    sources += [p for p in (PAPER / 'figures').rglob('*') if p.is_file()]
    assert all(p.stat().st_mtime <= pdf.stat().st_mtime for p in sources), 'PDF predates a local source/figure edit'
    provenance = json.loads((ROOT / 'artifacts/paper-build/official-20261115/provenance.json').read_text())
    styles = {name: sha(PAPER / name) for name in provenance['files']}
    assert all(styles[name] == data['official_sha256'] for name, data in provenance['files'].items())
    result = {'main_text_last_page': last_main, 'main_conclusion_page': conclusion[0],
              'main_conclusion_end_page': ending_pages[0], 'main_float_pages': float_pages, 'impact_statement_page': impact[0],
              'pdf_pages': len(doc), 'pdf_bytes': pdf.stat().st_size, 'pdf_sha256': sha(pdf),
              'font_types': font_types, 'all_fonts_embedded': embedded,
              'undefined_references': undefined, 'overfull_boxes': overfull,
              'metadata_author': doc.metadata['author'], 'source_freshness_verified': True,
              'official_template_sha256': styles, 'official_template_source': provenance['source'],
              'remaining_draft_items': ['anonymous artifact URL', 'authors final verification of AI disclosure and research'],
              'scope': 'Local manuscript only; source/PDF are not in Git or the anonymous code/data bundle. This is a formatting/build check, not independent scientific review. Main floats use caption-start matches; visual inspection remains necessary.'}
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps({k: result[k] for k in ('main_text_last_page', 'pdf_pages', 'font_types', 'all_fonts_embedded', 'undefined_references', 'overfull_boxes')}))


if __name__ == '__main__':
    main()
