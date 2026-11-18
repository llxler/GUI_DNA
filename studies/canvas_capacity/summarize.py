"""Derive interface and fixed-page counts without access to generated source or model replies."""
def summarize(probes, fixed, study):
    if fixed['primary_evaluation_sha256'] != study['source_sha256']['evaluation.json']:
        raise ValueError('Fixed-page results refer to a different evaluation')
    results = {}
    for rep in (1,2):
        library = probes['libraries'][str(rep)]
        variants = library.get('rows',[])
        first = next((row['responses'] for row in variants if row['label']=='example-0'),[])
        witnesses = []
        for row in variants:
            values = row.get('responses',[])
            if row['label'].startswith('field/') and (first,values) in [
                    ([True]*3,[False]*3),([False]*3,[True]*3)]:
                witnesses.append(row['label'])
        outcomes = {}
        for name in ('example-0','example-1','final-page'):
            rows = [r for r in fixed['rows'] if r['repetition']==rep and r['control']==name]
            assert len(rows) == len(study['milestones']) and {r['task'] for r in rows} == set(study['milestones'])
            outcomes[name] = {'observed':sum(r['passed'] is not None for r in rows),
                              'passed':sum(r['passed'] is True for r in rows)}
        available = study['groups'][f'plan-{rep}']['prepare_status']=='accepted'
        assert bool(variants) == available
        results[str(rep)] = {'library_available':available,'variants_tested':sum('responses' in r for r in variants),
            'variants_with_shooting':sum(r.get('responses') == [True]*3 for r in variants),
            'variants_unobservable':sum(None in r.get('responses',[]) for r in variants),
            'one_field_shooting_witnesses':witnesses,'fixed_pages':outcomes,
            'same_source_score_conflicts':[k for k in fixed['duplicate_conflicts'] if k.split('/')[0].endswith(f'-{rep}')]}
    return results
