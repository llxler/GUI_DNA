"""Read-only reconstruction of the November 17 studies and cost authorization."""
import json
from test.history_replay.run import ROOT, read, dump, sha, now
from test.webbench_draw.analyze import analyze as draw
from test.assertion_audit.analyze import analyze as assertion_audit
from test.authorized_costs import summarize
from test.ledger_read import totals
from test.draw_interface_audit import main as interface_audit


def main():
    values = {'draw':draw(), 'assertion_audit':assertion_audit()}
    interface_audit()
    interface = read(ROOT/'test/results/draw-interface-audit-20261117.json')
    cost = summarize('20261117')
    assert cost['exposure_usd'] <= 10
    assert all(s['stop_usd']==0 for s in cost['stages'].values())
    assert totals(ROOT/'artifacts/budget.sqlite3')['halted']==1
    report = {'verified_utc':now(),'all_passed':True,'costs':cost,
        'draw_candidates':values['draw']['observed_candidates'],
        'draw_reports':values['draw']['reports'],
        'assertion_audit_reports':len(values['assertion_audit']['rows']),
        'draw_interface_configurations':interface['legal_configurations'],
        'draw_interface_unchanged_javascript':interface['all_javascript_unchanged'],
        'source_recompilation':values['draw']['source_recompilation'],
        'third_round_halted':True,
        'summary_sha256':{name:sha(ROOT/name) for name in
            ('test/results/webbench-draw-20261117.json','test/results/assertion-audit-20261117.json',
             'test/results/draw-interface-audit-20261117.json')},
        'scope':'Original-workspace source/hash/report/ledger reconstruction; not an anonymous bundle or cross-machine browser replay.'}
    dump(ROOT/'test/results/replay-20261117.json',report)
    print(json.dumps(report,indent=2))


if __name__=='__main__':
    main()
