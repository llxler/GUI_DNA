"""Visualize current-file versus same-page full-history observations."""
import hashlib
import json
from pathlib import Path
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.colors import ListedColormap, BoundaryNorm
from matplotlib.patches import Patch
import cairosvg

ROOT=Path(__file__).resolve().parents[1]


def main():
    source=ROOT/'test/results/history-replay.json'
    records=json.loads(source.read_text())['rows']
    records=[r for r in records if r['cohort']=='expansion' and r['label']=='final' and r['method'] in ('plan','free_lib')]
    assert len(records)==480
    colors=['#e5e7eb','#d99736','#557bc2','#167c75']
    names=['Neither endpoint','Current file only','Full history only','Both endpoints']
    cmap=ListedColormap(colors);norm=BoundaryNorm([-.5,.5,1.5,2.5,3.5],4)
    plt.rcParams.update({'font.size':9,'svg.fonttype':'path'})
    fig,axes=plt.subplots(3,1,figsize=(7.2,6.5),sharex=True)
    encoded=[]
    for ax,project in zip(axes,('calculator','table','bom')):
        matrix=[];labels=[]
        for builder,bname in [('openai/gpt-5','GPT-5'),('anthropic/claude-sonnet-4.5','Sonnet')]:
            for method,mname in [('free_lib','Code'),('plan','Plan')]:
                for model,pname in [('openai/gpt-oss-120b','OSS'),('mistralai/mistral-small-3.2-24b-instruct','Mistral')]:
                    group=sorted([r for r in records if r['project']==project and r['builder']==builder and r['method']==method and r['model']==model],
                                 key=lambda r:int(r['task'].split('-')[1]))
                    assert len(group)==20
                    values=[int(r['old_current_passed'])+2*int(r['history_passed']) for r in group]
                    matrix.append(values);labels.append(f'{bname} / {mname} / {pname}')
                    encoded.append({'project':project,'builder':builder,'method':method,'model':model,'states':values})
        ax.imshow(matrix,aspect='auto',cmap=cmap,norm=norm,interpolation='nearest')
        ax.set_yticks(range(8),labels,fontsize=8)
        ax.set_title(project,loc='left',fontweight='bold',fontsize=10)
        ax.set_xticks([i-.5 for i in range(21)],minor=True)
        ax.set_yticks([i-.5 for i in range(9)],minor=True)
        ax.grid(which='minor',color='white',linewidth=.65);ax.tick_params(which='both',length=0)
        for spine in ax.spines.values():spine.set_visible(False)
    axes[-1].set_xticks(range(20),[str(i) for i in range(1,21)])
    axes[-1].set_xlabel('Prefix length k (distinct saved page C_k per column)',fontsize=8)
    fig.legend(handles=[Patch(facecolor=c,label=n) for c,n in zip(colors,names)],loc='lower center',ncol=4,
               frameon=False,bbox_to_anchor=(.53,.005),fontsize=7)
    fig.subplots_adjust(left=.30,right=.99,bottom=.14,top=.95,hspace=.35)
    out=ROOT/'DNA_latex/figures/history_endpoint_map';out.parent.mkdir(parents=True,exist_ok=True)
    fig.savefig(out.with_suffix('.svg'));cairosvg.svg2pdf(url=str(out.with_suffix('.svg')),write_to=str(out.with_suffix('.pdf')))
    preview=ROOT/'artifacts/review-20261116/paper-preview/history-endpoints.png';preview.parent.mkdir(parents=True,exist_ok=True)
    fig.savefig(preview,dpi=160);plt.close(fig)
    counts={names[i]:sum(row['states'].count(i) for row in encoded) for i in range(4)}
    from collections import defaultdict,Counter
    pairs=defaultdict(dict)
    for row in records:pairs[(row['project'],row['builder'],row['model'],row['task'])][row['method']]=row
    paired={}
    for endpoint in ('old_current_passed','history_passed'):
        paired[endpoint]=dict(Counter(('both' if p['plan'][endpoint] and p['free_lib'][endpoint] else
            'plan_only' if p['plan'][endpoint] else 'code_only' if p['free_lib'][endpoint] else 'neither') for p in pairs.values()))
    result={'source':str(source.relative_to(ROOT)),'source_sha256':hashlib.sha256(source.read_bytes()).hexdigest(),
        'cells':480,'counts':counts,'rows':encoded,'paired_outcomes':paired,
        'scope':'Same saved sources, historical current-file and later full-history observations; columns are correlated task prefixes, not a trajectory of one immutable program. Glyph outlines, no rasterized text in the PDF.'}
    (ROOT/'test/results/history-endpoint-figure.json').write_text(json.dumps(result,indent=2)+'\n')
    print(counts)


if __name__=='__main__':main()
