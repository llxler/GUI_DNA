"""Compare the function declarations and dispatch lines in each fixed/planned controller."""
from argparse import ArgumentParser
from collections import Counter
from difflib import SequenceMatcher
from pathlib import Path
import re

from studies.study_io import ROOT,dump,read,sha
from . import run

OUTPUT=Path(__file__).with_name('function-choices.json')
NAME=re.compile(r'\bfunction\s+([\w$]+)\s*\(')


def reconstruct():
    measurements=read(run.HERE/'result.json')['models']
    out={}
    for tag,model in read(run.OUT/'registration.json')['models'].items():
        seal=run.OUT/tag/'seal.json';data=read(seal)
        assert measurements[model]['seal']==sha(seal)
        results={(r['task'],r['arm']):r for r in measurements[model]['rows']}
        cases={}
        for task,rows in data['rows'].items():
            programs=[]
            for a in ('fixed-gpt5-library','gpt5-library'):
                r=rows[a];file=ROOT/r['file']
                assert r['status']=='valid' and sha(file)==r['files_sha256']==results[task,a]['files_sha256']
                programs.append(read(file)['candidate.js'].splitlines())
            before,after=programs
            declarations=[set(NAME.findall('\n'.join(lines))) for lines in programs]
            by_type=Counter()
            for op,i,j,k,l in SequenceMatcher(None,before,after,autojunk=False).get_opcodes():
                if op=='equal':continue
                for line in before[i:j]+after[k:l]:
                    key='function' if NAME.match(line.strip()) else ('dispatch' if line.strip().startswith('case ') else 'other')
                    by_type[key]+=1
            cases[task]=dict(fixed_passed=results[task,'fixed-gpt5-library']['passed'],planned_passed=results[task,'gpt5-library']['passed'],
                             fixed_unique=sorted(declarations[0]-declarations[1]),planned_unique=sorted(declarations[1]-declarations[0]),
                             changed_lines_by_kind=dict(by_type),fixed_file=rows['fixed-gpt5-library']['files_sha256'],
                             planned_file=rows['gpt5-library']['files_sha256'])
        out[model]=cases
    return out

if __name__=='__main__':
    parser=ArgumentParser(description=__doc__);parser.add_argument('--write',action='store_true')
    args=parser.parse_args();result=reconstruct()
    if args.write:dump(OUTPUT,result)
    assert result==read(OUTPUT)
