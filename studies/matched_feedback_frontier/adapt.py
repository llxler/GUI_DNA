"""Scoped runtime adapter; the shared frozen source files remain unchanged."""
from contextlib import contextmanager
from pathlib import Path
from studies.study_io import ROOT, read, sha

HERE=Path(__file__).resolve().parent
OUT=ROOT/'artifacts/matched-feedback-frontier-20261116'


def configuration():
    return {'models':['openai/gpt-5'],'temperature':.6,'max_tokens':20000,'max_repairs':2,
        'budget_usd':3.5,'stop_new_requests_usd':3.2,
        'price_caps_per_million':{'prompt':1.25,'completion':10},
        'model_price_caps':{'openai/gpt-5':{'prompt':1.25,'completion':10}},
        'reasoning_effort':{'openai/gpt-5':'medium'},'omit_params':{'openai/gpt-5':['temperature','seed']},
        'provider_order':{'openai/gpt-5':['OpenAI']}}


def verify():
    from test.matched_feedback.core import verify as shared_verify
    shared_verify()
    for path,expected in read(OUT/'shared-dependencies.json')['sha256'].items():
        assert sha(ROOT/path)==expected,path


@contextmanager
def configured():
    from test.matched_feedback import core,browser,prepare,run
    modules=(core,browser,prepare,run)
    changes=[]
    def change(module,name,value):
        changes.append((module,name,getattr(module,name)));setattr(module,name,value)
    for module in modules:
        if hasattr(module,'OUT'):change(module,'OUT',OUT)
        if hasattr(module,'configuration'):change(module,'configuration',configuration)
    change(core,'MODELS',('openai/gpt-5',));change(core,'SEEDS',(2026111603,))
    change(prepare,'HERE',HERE)
    try:yield modules
    finally:
        for module,name,old in reversed(changes):setattr(module,name,old)
