from test.interface_blind_run_helpers import output_files


def test_unrestricted_baseline_can_reuse_and_replace_frozen_files():
    library = {'files': {'runtime.js': 'frozen implementation', 'style.css': 'old style'}}
    result = output_files('free_lib', library, {'files': {'index.html': '<script src="runtime.js"></script>', 'style.css': 'new style'}})
    assert result['runtime.js'] == 'frozen implementation'
    assert result['style.css'] == 'new style'
    assert library['files']['style.css'] == 'old style'
    assert output_files('free', None, {'files': {'index.html': 'from scratch'}}) == {'index.html': 'from scratch'}
