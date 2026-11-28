"""Replay the archived Flash upgrade operation against both original page bytes."""
from argparse import ArgumentParser
from collections import Counter

from studies.study_io import ROOT, dump, read, sha
from ..component_contracts import report as history
from ..functional_pilot import evaluate, pages, schema
from . import generate

RESULT = generate.HERE/'sdk-audit.json'
SITE = '000011'
MODEL = 'deepseek-flash'


def inspect(engine, records):
    def resources(tab):
        # AMIS can render the header and body in separate tables until layout settles.
        # Only the resource rows are relevant to a change in state.
        return tab.wait_for_function("""() => {
            const resources = {};
            for (const row of document.querySelectorAll('table tr')) {
                if (!row.getBoundingClientRect().height) continue;
                const cells = Array.from(row.querySelectorAll('td')).map(x => x.innerText.trim());
                if (['Gold','Iron','Wood','Wheat'].includes(cells[0])) {
                    resources[cells[0]] = Number(cells[1].replace(/,/g, ''));
                }
            }
            return Object.keys(resources).length === 4 && resources;
        }""").json_value()
    snapshots = {}
    for arm in ('direct','human'):
        record = records[arm]
        source = ROOT/record['file']
        assert sha(source) == record['sha256']
        with pages.local_tab(engine, source.read_text(), sdk=arm=='human') as tab:
            if arm=='human':
                tab.get_by_text('City Overview',exact=True).click()
                before = resources(tab)
                tab.get_by_text('Upgrades',exact=True).click()
                tab.locator('.cxd-Select-placeholder:visible').click()
                tab.locator('.cxd-Select-option-content[title="Marketplace"]:visible').click()
                tab.get_by_text('Upgrade Now',exact=True).click()
                tab.get_by_text('City Overview',exact=True).click()
                after = resources(tab)
                snapshots[arm] = dict(before=before,after=after,action='Purchase the Marketplace upgrade')
            else:
                labels = {'gold':'#statGold','iron':'#statIron','wood':'#statWood','city_level':'#statCityLvl'}
                def visible_state():
                    return {k:int(tab.locator(s).inner_text()) for k,s in labels.items()}
                before = visible_state()
                tab.locator('a[data-page=upgrades]').click()
                tab.locator('#upgradeCityBtn').click()
                after = visible_state()
                snapshots[arm] = dict(before=before,after=after,action='Upgrade the city')
            snapshots[arm]['candidate'] = record
    return snapshots


def audit():
    import duckdb
    original = history.STAGES[-1][1]
    records = read(original)['development'][MODEL][SITE]
    cfg = read(generate.native.OUT/'plans'/MODEL/SITE/'record.json')['config']
    assert pages.page(cfg,'human').encode() == (ROOT/records['human']['file']).read_bytes()
    block = next(t for t in cfg['body'][0]['tabs'] if t['title']=='Upgrades')
    form = next(b for b in block['body'] if b['type']=='form')
    _, old = history.website_groups()
    by_key = {(r['site'],r['check'],r['arm']):r for r in old if r['model']==MODEL}
    status = Counter()
    for (site,check,arm), direct in by_key.items():
        if arm!='direct':
            continue
        human = by_key[site,check,'human']
        status[('yes' if direct['verdict']=='YES' else 'other')+'_'+('yes' if human['verdict']=='YES' else 'other')] += 1
    steps = duckdb.sql('select ui_instruct from read_parquet(?) where id=?',
                       params=[str(generate.gen.SRC),SITE]).fetchall()[0][0]
    trial = evaluate.browser_job(lambda e:inspect(e,records))
    assert trial['human']['before']==trial['human']['after']
    assert trial['direct']['after']['city_level']==trial['direct']['before']['city_level']+1
    assert trial['direct']['after']['gold']<trial['direct']['before']['gold']
    control = pages.check(pages.page(schema.SAMPLE,'human'),True)
    assert all(control['checks'].values())
    return dict(site=SITE,model=MODEL,operation=1,task=steps[1]['task'],expected=steps[1]['expected_result'],
                candidates=sha(original),sdk_distribution=sha(generate.gen.DIST),sdk_public=control,
                generator_plan=sha(generate.native.OUT/'plans'/MODEL/SITE/'record.json'),
                original_verdicts={a:by_key[SITE,1,a]['verdict'] for a in ('direct','human')},
                form_submit_events=form['onEvent'],native_replay=trial,paired_across_nine=dict(sorted(status.items())))


if __name__ == '__main__':
    parser=ArgumentParser(description=__doc__)
    parser.add_argument('--write',action='store_true')
    args=parser.parse_args()
    result=audit()
    if args.write and not RESULT.exists():
        dump(RESULT,result)
    assert read(RESULT)==result
    print('Verified original page hashes, five SDK controls and a paired resource-state replay.')
