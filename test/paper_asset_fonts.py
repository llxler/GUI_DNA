"""Re-export existing paper figures with vector-outlined labels and no Type 3 fonts.

No saved browser observations or experiment code are changed.
"""
from pathlib import Path
import sys
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.image as mpimg

ROOT=Path(__file__).resolve().parents[1]


def main():
    plt.rcParams.update({'pdf.fonttype':42,'ps.fonttype':42})
    from test.webbench_dna.taskmap_figure import main as taskmap
    sys.argv=[sys.argv[0]]
    taskmap()
    fig,axes=plt.subplots(1,2,figsize=(12,3.8))
    for axis,method,title in zip(axes,['free','dna'],['Free code: nesting fails','GUI-DNA: nesting passes']):
        axis.imshow(mpimg.imread(ROOT/'artifacts/failure-figure'/f'{method}.png'))
        axis.set_title(title,fontsize=12);axis.axis('off')
    fig.tight_layout();fig.savefig(ROOT/'DNA_latex/figures/failure-case.pdf',bbox_inches='tight');plt.close(fig)
    # Preserve vector curves and raster screenshots; outline figure labels to
    # satisfy the official Type-1-only PDF rule without rasterizing charts.
    import pymupdf
    import cairosvg
    from io import BytesIO
    folder=ROOT/'DNA_latex/figures'
    for name in ('webbench_taskmap.pdf','failure-case.pdf','matched_prefix_endpoints.pdf'):
        path=folder/name
        document=pymupdf.open(path)
        assert len(document)==1
        svg=document[0].get_svg_image(text_as_path=True)
        document.close()
        result=cairosvg.svg2pdf(bytestring=svg.encode())
        check=pymupdf.open(stream=result,filetype='pdf')
        assert not check[0].get_fonts(), name
        path.write_bytes(result)
    print('Re-exported labels as vector paths; retained screenshot pixels and outcomes.')


if __name__=='__main__':main()
