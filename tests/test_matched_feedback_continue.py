"""Budget continuation must replay exact inputs without an extra API call."""
import json
import pytest
from test.matched_feedback_continue.run import ReplayClient


def saved(folder,actual=1):
    folder.mkdir()
    thread=[{'role':'user','content':'same public requirement'}]
    (folder/'request.json').write_text(json.dumps({'call_id':'old','body':{'model':'openai/gpt-5','messages':thread}}))
    (folder/'response.json').write_text(json.dumps({'choices':[{'message':{'content':'retained output'}}]}))
    class NoCalls:
        def call(self,*args,**kwargs):raise AssertionError('Replay must not send a request')
    return ReplayClient(NoCalls(),[{'id':'old','actual':actual}]),thread


def test_complete_response_reuses_exact_original_messages(tmp_path):
    client,thread=saved(tmp_path/'call')
    assert client.call('openai/gpt-5',thread,tmp_path/'call','unused',seed=2026111603)=='retained output'
    with pytest.raises(AssertionError,match='input changed'):
        client.call('openai/gpt-5',[{'role':'user','content':'changed'}],tmp_path/'call','unused')


def test_unknown_reservation_never_becomes_a_free_replay(tmp_path):
    client,thread=saved(tmp_path/'call',actual=None)
    with pytest.raises(AssertionError,match='Uncertain request'):
        client.call('openai/gpt-5',thread,tmp_path/'call','unused')
