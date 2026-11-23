"""Separate metered API reservations from subscription inference during library refinement."""
import argparse
from decimal import Decimal
from studies.ledger_read import totals
from studies.study_io import ROOT,dump,read,sha

RESULT=ROOT/'studies/results/library-refinement-accounting-20261123.json'
ART=ROOT/'artifacts'


def sum_costs(items,key):
    return str(sum(Decimal(str(i[key])) for i in items).quantize(Decimal('.000001')))


def reconstruct():
    snapshot=ART/'editorial-20261123/closing-accounting.json'
    earlier=read(snapshot)
    stages=('contract-library-table-20261123','library-refinement-chart-20261123')
    charges={name:totals(ART/name/'budget.sqlite3') for name in stages}
    all_today={**{name:totals(ART/name/'budget.sqlite3') for name in earlier['ledgers']},**charges}
    assert all(all_today[name]==data for name,data in earlier['ledgers'].items())
    def amounts(stages):
        return {'calls':sum(r['calls'] for r in stages.values()),'unsettled_calls':sum(r['unsettled_calls'] for r in stages.values()),
                **{k:sum_costs(stages.values(),k) for k in ('settled_usd','exposure_usd')}}
    subscription={}
    for stage in ('compatible-library-rebuild-20261123','compatible-chart-rebuild-20261123','public-controller-table-20261123'):
        seal=ART/stage/'sealed.json'
        items={}
        for source in sorted((ART/stage).glob('*/status.json')):
            data=read(source)
            items[source.parent.name]={'status':data['status'],'input_tokens':sum(v['input_tokens'] for v in data['usage']),
                                       'output_tokens':sum(v['output_tokens'] for v in data['usage']),'sha256':sha(source)}
        subscription[stage]={'build_seal_sha256':sha(seal),'calls':len(items),'calls_by_arm':items}
    return {'metered_currency':'USD','incremental_stages':charges,'incremental_total':amounts(charges),
            'whole_session_total':amounts(all_today),'earlier_ledger_summary_sha256':sha(snapshot),
            'subscription_builds':subscription,'subscription_pricing':'Usage recorded in tokens. Marginal USD per subscription call is unavailable.',
            'local_inference':'GPU inference has zero remote API requests. Electricity and equipment costs were not measured.'}


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--check',action='store_true')
    args=p.parse_args()
    data=reconstruct()
    if args.check or RESULT.exists():
        assert read(RESULT)==data
    else:
        dump(RESULT,data)
    print(data['incremental_total'], data['whole_session_total'])
