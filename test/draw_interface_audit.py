"""Post-hoc finite audit of the draw/GPT-5 styling-only compiler outputs.

This checks generated file bytes, not browser behavior or functional reachability.
"""
from itertools import product
from test.history_replay.run import ROOT, read, sha, digest, dump, now
from test.webbench_draw.core import BUILD, slug, compile_plan


def main():
    path=BUILD/'libraries'/slug('openai/gpt-5')/'package.json'
    package=read(path)
    properties=package['plan_schema']['properties']
    assert set(properties)=={'theme','labelSize'}
    assert package['plan_schema']['required']==[]
    assert properties['theme']=={'type':'string','enum':['light','dark']}
    assert properties['labelSize']=={'type':'integer','minimum':28,'maximum':80}
    themes=[None,*properties['theme']['enum']]
    labels=[None,*range(properties['labelSize']['minimum'],properties['labelSize']['maximum']+1)]
    rows=[]
    registration=ROOT/'artifacts/webbench-draw-interface-audit-20261117/registration.json'
    value={'scope':'Post-hoc inspection of the proposed interface; exact file-byte enumeration only, no behavioral scoring.',
        'package_sha256':sha(path),'script_sha256':sha(__file__),
        'plans':[dict((k,v) for k,v in [('theme',theme),('labelSize',label)] if v is not None)
            for theme,label in product(themes,labels)]}
    if registration.exists():
        assert read(registration)['specification']==value
    else:
        dump(registration,{'registered_utc':now(),'specification':value})
    for plan in value['plans']:
        files=compile_plan(package,plan)
        rows.append({'plan':plan,'output_sha256':digest(files),
            'file_hashes':{name:digest(text) for name,text in files.items()},
            'javascript_matches_frozen':all(files[name]==package['files'][name] for name in ('index.js','app.js'))})
    result={'package_sha256':sha(path),'script_sha256':sha(__file__),'legal_configurations':len(rows),
        'distinct_source_maps':len({r['output_sha256'] for r in rows}),
        'all_javascript_unchanged':all(r['javascript_matches_frozen'] for r in rows),
        'variants_per_file':{name:len({r['file_hashes'][name] for r in rows}) for name in rows[0]['file_hashes']},
        'scope':value['scope'],'limitation':'HTML/CSS differences can affect interaction geometry; unchanged JavaScript does not prove identical behavior. This is not a browser reachability bound.',
        'rows':rows}
    dump(ROOT/'test/results/draw-interface-audit-20261117.json',result)
    print({key:result[key] for key in ('legal_configurations','distinct_source_maps','all_javascript_unchanged','variants_per_file')})


if __name__=='__main__':
    main()
