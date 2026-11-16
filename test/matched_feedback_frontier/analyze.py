"""Reconstruct the frontier cohort, retaining its separate sample denominator."""
from test.history_replay.run import ROOT,dump
from .adapt import configured,OUT


def effective_out():
    from test.matched_feedback_continue.run import OUT as resumed
    return resumed if (resumed/'continuation.json').exists() else OUT


def reconstruct():
    context=configured
    if effective_out()!=OUT:
        from test.matched_feedback_continue.run import configured as context
    with context() as modules:
        result=modules[5].reconstruct()
    assert result['candidates']==15
    result['scope']='Exploratory GPT-5 medium replication with one request chain per condition, no transmitted seed or temperature. Same public feedback and per-response cap; actual computation differs. Three no-library and six candidates per same-library method. Separate from the two-repeat GPT-OSS cohort; no pure reasoning/model effect or broad generalization claim.'
    return result


if __name__=='__main__':
    result=reconstruct();dump(ROOT/'test/results/matched-feedback-frontier.json',result)
    print(result['groups']);print(result['cost'])
