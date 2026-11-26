"""Check the current local PDF against source freshness and publication format.

Run with: uv run --with pymupdf python -m studies.paper_format
This checks build/format evidence, not scientific validity or human review.
"""
import hashlib
import argparse
import json
from pathlib import Path
import re
import unicodedata

import pymupdf

ROOT = Path(__file__).resolve().parents[1]
PAPER = ROOT / 'DNA_latex'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def expand(text):
    return re.sub(r'\\input\{([^}]+)\}',
                  lambda m: expand((PAPER / (m.group(1) + '.tex')).read_text()), text)


def search_text(text):
    # PDF extraction may retain ligatures such as the fl in "workflow".
    text = unicodedata.normalize('NFKC', text).replace('’', "'").replace('-\n', '')
    return ' '.join(text.split())


def export_primary_table(doc, page_number, destination):
    """Export the full-width caption, table panels and explanatory note as one vector page."""
    page = doc[page_number - 1]
    caption = page.search_for('Table 1.')[0]
    footer, = [block for block in page.get_text('blocks')
               if 'Direct writes code without a library.' in block[4]]
    rule = next(drawing['rect'] for drawing in page.get_drawings()
                if caption.y1 < drawing['rect'].y0 < footer[3]
                and drawing['rect'].width > page.rect.width * 0.75)
    # PyMuPDF can split the note after superscripts. Locate its final words from the
    # generated table so the exported page contains every protocol qualifier.
    table_source = (PAPER / 'end_to_end_table.tex').read_text()
    note = table_source.split('Direct writes code without a library.', 1)[1].split(r'\end{minipage}', 1)[0]
    ending = ' '.join(re.findall(r'[A-Za-z]+', note)[-5:])
    final_lines = [rect for rect in page.search_for(ending) if rect.y1 >= footer[1]]
    if not final_lines:
        raise ValueError(f'Cannot locate the end of the Table 1 note: {ending}')
    bottom = max(footer[3], max(rect.y1 for rect in final_lines))
    clip = pymupdf.Rect(rule.x0 - 5, caption.y0 - 5, rule.x1 + 5, bottom + 5)
    destination.mkdir(parents=True, exist_ok=True)
    with pymupdf.open() as single, pymupdf.open() as export:
        single.insert_pdf(doc, from_page=page.number, to_page=page.number)
        source = single[0]
        source.clip_to_rect(clip)
        source.set_cropbox(clip)
        table = export.new_page(width=clip.width, height=clip.height)
        table.show_pdf_page(table.rect, single, 0)
        assert ending in search_text(table.get_text()), 'Table 1 note is clipped'
        export.save(destination / 'table-1.pdf', garbage=4, deflate=True)
        table.get_pixmap(matrix=pymupdf.Matrix(2.65, 2.65)).save(destination / 'table-1.png')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--report', type=Path, default=ROOT / 'test/results/paper-format-20261115.json')
    parser.add_argument('--table-preview', type=Path, help='Export the verified Table 1 as PDF and PNG to this directory.')
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
    ending_pages = [i + 1 for i, text in enumerate(pages) if search_text(ending) in search_text(text)]
    assert len(ending_pages) == 1, 'Locate the end, not just the heading, of the main text'
    # ICML sets the caption label in italics. A prose cross-reference may
    # also begin a line with "Table 1." and precede the actual table.
    captions = {}
    for number, page in enumerate(doc, start=1):
        for block in page.get_text('dict')['blocks']:
            for line in block.get('lines', []):
                spans = line['spans']
                if not spans or not spans[0]['flags'] & pymupdf.TEXT_FONT_ITALIC:
                    continue
                text = ''.join(span['text'] for span in spans)
                label = re.match(r'^(Table|Figure)\s+(\d+)\.', text)
                if label:
                    captions.setdefault(f'{label[1]} {label[2]}', []).append(number)
    float_pages = {}
    for kind, count in [('Table', table_count), ('Figure', figure_count)]:
        for number in range(1, count + 1):
            key = f'{kind} {number}'
            assert len(captions.get(key, [])) == 1, (key, captions.get(key))
            float_pages[key] = captions[key][0]
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
    if args.table_preview:
        export_primary_table(doc, float_pages['Table 1'], args.table_preview)
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps({k: result[k] for k in ('main_text_last_page', 'pdf_pages', 'font_types', 'all_fonts_embedded', 'undefined_references', 'overfull_boxes')}))


if __name__ == '__main__':
    main()
