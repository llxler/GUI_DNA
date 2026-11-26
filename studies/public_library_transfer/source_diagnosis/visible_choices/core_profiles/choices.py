"""Link each emitted controller to the selected Boolean flags and their public checks."""
from argparse import ArgumentParser
from pathlib import Path

from studies.study_io import ROOT,dump,read,sha
from . import run

OUTPUT=Path(__file__).with_name('configurations.json')


def reconstruct():
    data={}
    for tag,model in read(run.OUT/'registration.json')['models'].items():
        source=run.OUT/tag/'seal.json'
        sealed=read(source)
        assert sealed['prior']==sha(run.parent.OUT/tag/'seal.json')
        flags=read(run.OUT/tag/'profiles.json')
        codes={tuple(sorted(r['choices'].items())):r for r in flags['enumerated']}
        _,compile_plan=run.resources(tag)
        targets={}
        for task,rows in sealed['rows'].items():
            raw=run.parent.OUT/tag/task/'self/call'
            response=sorted(raw.glob('transmission-*/settled.json'))[0]
            file=response.with_name('response.json')
            assert read(response)['response_sha256']==sha(file)
            old=None
            if rows['unfiltered']['status']=='valid':
                text=read(file)['choices'][0]['message']['content']
                old=(run.parent.recovery.web if tag=='qwen9' else run.parent.SUITE).parse_json(text)
                assert compile_plan(old)==read(ROOT/rows['unfiltered']['file'])['candidate.js']
            values={'before':old}
            for label,key in [('model','self'),('nearest','projected'),('fixed','fixed-core')]:
                r=rows[key]
                if r['status']!='valid':
                    values[label]=None
                    continue
                p=flags['eligible'][r['choice']]
                assert read(ROOT/r['file'])['candidate.js']==compile_plan(p)
                values[label]=p
            values['failed_common_before']=None if old is None else sorted(k for k,b in codes[tuple(sorted(old.items()))]['checks'].items() if not b)
            values['original_response_sha256']=sha(file)
            targets[task]=values
        data[model]=dict(seal=sha(source),targets=targets)
    return data


if __name__=='__main__':
    parser=ArgumentParser(description=__doc__);parser.add_argument('--write',action='store_true')
    args=parser.parse_args();value=reconstruct()
    if args.write:dump(OUTPUT,value)
    assert read(OUTPUT)==value
