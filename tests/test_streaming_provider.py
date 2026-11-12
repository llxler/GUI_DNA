import pytest
from gui_dna.provider import ProviderError
from test.streaming_provider import assemble_chunks
from test.streaming_provider_v2 import assemble_chunks as assemble_checked_chunks


def test_provider_error_finish_is_not_a_model_result_even_with_done():
    chunks = [{'choices': [{'index': 0, 'delta': {'content': '{"partial":'}, 'finish_reason': 'error'}],
               'usage': {'cost': 0}}]
    with pytest.raises(ProviderError, match='not a model result'):
        assemble_checked_chunks(chunks, done=True)


def test_usage_only_terminal_chunk_does_not_erase_content():
    chunks = [{'id': 'fake', 'choices': [{'delta': {'content': '{"x":'}, 'finish_reason': None}]},
              {'choices': [{'delta': {'content': '1}'}, 'finish_reason': 'stop'}]},
              {'choices': [], 'usage': {'cost': .01}}]
    result = assemble_chunks(chunks, True)
    assert result['choices'][0]['message']['content'] == '{"x":1}'
    assert result['usage']['cost'] == .01
    assert result['id'] == 'fake'


def test_partial_or_unbilled_stream_is_not_a_model_output():
    chunks = [{'choices': [{'delta': {'content': '{}'}, 'finish_reason': 'stop'}]}]
    with pytest.raises(ProviderError, match='terminal'):
        assemble_chunks(chunks, False)
    with pytest.raises(ProviderError, match='billed cost'):
        assemble_chunks(chunks, True)
