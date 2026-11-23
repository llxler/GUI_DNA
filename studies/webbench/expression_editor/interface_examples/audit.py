"""Verify the original and appended requests, receipts and current-file reports read-only."""
from collections import Counter

from gui_dna.provider import parse_json
from studies.ledger_read import calls, totals
from studies.study_io import digest, read, sha, source_files
from studies.table_library_sources.run import verify
from .run import BASELINE, CONTROL, DEST, EXAMPLE, MODEL, OUT, TASKS, TRIAL, intervention, summary


def check():
    public=read(DEST)
    assert public['audit_sha256']=={
        'freeze':sha(OUT/'freeze.json'),'generated':sha(OUT/'generation-complete.json'),
        'scores':sha(OUT/'scores-complete.json'),'primary':sha(BASELINE),'fixed_control':sha(CONTROL)}
    frozen=read(OUT/'freeze.json')
    generated=read(OUT/'generation-complete.json')
    verify(frozen['inputs_sha256'])
    verify(generated['files_sha256'])
    assert generated['freeze_sha256']==public['audit_sha256']['freeze']
    ledger_rows={r['id']:r for r in calls(OUT/'budget.sqlite3')}
    assert totals(OUT/'budget.sqlite3')==public['ledger']
    used=set()
    providers=Counter()
    unique_pages=set()
    baseline=read(BASELINE)['targets']
    controls=read(CONTROL)['targets']
    package=read(TRIAL/'reference.json')
    for task in TASKS:
        old=read(TRIAL/'candidates/reference'/task/'first/call/request.json')['body']
        row=public['targets'][task]
        assert row['original']==baseline[task]['reference']['first']
        for c in ('reference_full','empty_plan'):
            assert row[c]==controls[task][c]
        new=OUT/'candidates/reference'/task/'first'
        record=read(new/'record.json')
        actual=row['appended']
        request=new/'call/request.json'
        if request.exists():
            request=read(request)
            identifier=request['call_id']
            assert identifier not in used and ledger_rows[identifier]['model']==MODEL
            used.add(identifier)
            new_body=request['body']
            assert new_body['messages']==intervention(old['messages'],package['plan_schema'])
            assert {k:v for k,v in old.items() if k!='messages'}=={k:v for k,v in new_body.items() if k!='messages'}
            if record['response']:
                response=read(new/'call/response.json')
                assert ledger_rows[identifier]['actual'] is not None
                providers[response.get('provider','unspecified')]+=1
        assert (record['response'],record['valid'])==(actual['response'],actual['valid'])
        if record['valid']:
            parsed=parse_json(response['choices'][0]['message']['content'])
            assert actual['equals_empty_example']==(parsed==EXAMPLE)
            expected=source_files(new/'page')
            assert expected==record['files_sha256']
            unique_pages.add(digest(expected))
            score=read(OUT/'scores'/task/'score.json')
            assert set(score['tests'])=={task} and score['all_passed']==actual['passed']
            assert sha(OUT/'scores'/task/'report.json')==score['report_sha256']==actual['official_report_sha256']
        else:
            assert actual['passed']==(False if record['response'] else None)
    assert set(ledger_rows)==used and public['summary']==summary(public['targets'])
    return {'verified_requests':len(used),'unique_pages':len(unique_pages),'providers':dict(providers)}


if __name__=='__main__':
    print(check())
