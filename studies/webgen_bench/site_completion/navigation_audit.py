"""Separate an unreachable-by-judge ranking check from the missing upgrade effect."""
from argparse import ArgumentParser

from studies.study_io import ROOT, dump, read, sha
from ..component_contracts import report as history
from ..functional_pilot import evaluate, pages, voyager
from . import sdk_audit

RESULT = sdk_audit.RESULT.with_name('navigation-audit.json')


def observe(engine, html):
    with pages.local_tab(engine,html,sdk=True) as tab:
        ranking = tab.get_by_text('Rankings',exact=True)
        ranking.wait_for(state='attached')
        tab.wait_for_timeout(400)
        labels=voyager.Labels(tab)
        labels.observe()
        state=ranking.evaluate("""el => {
            const box=el.getBoundingClientRect();
            const midX=box.x+box.width/2, midY=box.y+box.height/2;
            const point=document.elementFromPoint(midX,midY);
            return {inside_viewport:midX>=0 && midX<innerWidth && midY>=0 && midY<innerHeight,
              labelled:window.__wgItems.some(x=>x===el || x.contains(el) && x.textContent.trim()==='Rankings'),
              hittable:!!point && (point===el || el.contains(point))};
        }""")
        labels.clear()
        ranking.click()
        tab.get_by_text('Aetheria',exact=True).wait_for()
        table=tab.wait_for_function("""() => {
            const rows=[...document.querySelectorAll('table tr')].filter(r=>r.getBoundingClientRect().height)
              .map(r=>[...r.querySelectorAll('td')].map(c=>c.innerText.trim()))
              .filter(c=>c.length===6 && /^[1-5]$/.test(c[0]));
            return rows.length===5 && rows;
        }""").json_value()
        return state, [{'rank':int(row[0]),'name':row[1],'gold':int(row[3].replace(',',''))} for row in table]


def reconstruct():
    case=read(sdk_audit.RESULT)
    r=case['native_replay']['human']['candidate']
    source=ROOT/r['file']
    assert sha(source)==r['sha256']
    _,rows=history.website_groups()
    old=next(row for row in rows if row['model']==case['model'] and row['arm']=='human' and row['site']==case['site'] and row['check']==2)
    trail=ROOT/'artifacts/webgen-native-judge-20261126pm/checks'/case['model']/case['site']/'2/human/judgment.json'
    assert old['source']==sha(trail) and old['verdict']==read(trail)['verdict']=='NO'
    initial,rank=evaluate.browser_job(lambda engine:observe(engine,source.read_text()))
    assert [r['rank'] for r in rank]==list(range(1,6)) and len({r['name'] for r in rank})==5
    assert [r['gold'] for r in rank]==sorted((r['gold'] for r in rank),reverse=True)
    return dict(site=case['site'],arm='human',check=2,model=case['model'],candidate=r['sha256'],original_verdict=old['verdict'],
                original_judgment=sha(trail),original_steps=len(read(trail)['trail']),initial_ranking_tab=initial,
                browser_action='Activate the Rankings tab by exact DOM label',visible_ranked_rows=rank)


if __name__=='__main__':
    parser=ArgumentParser(description=__doc__)
    parser.add_argument('--write',action='store_true')
    args=parser.parse_args()
    data=reconstruct()
    if args.write and not RESULT.exists():
        dump(RESULT,data)
    assert data==read(RESULT)
    print('Replayed the five visible ranking records against the original NO verdict.')
