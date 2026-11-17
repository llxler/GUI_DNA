"""Offline checks for the WebApp1K plan compiler (no API, no Jest).  Run: uv run pytest test/webapp1k_dna -q"""
import pytest

from test.webapp1k_dna import compiler

ATOM_A = """import React, { useState } from 'react';
const A = () => {
  const [msg, setMsg] = useState('');
  return (<form onSubmit={async (e) => { e.preventDefault(); setMsg('Canonical URL updated successfully'); }}>
    <h2>Edit Post Settings</h2>
    <label htmlFor="u">Canonical URL</label><input id="u" placeholder="Enter URL" />
    <button type="submit">Save</button>{msg && <p>{msg}</p>}
  </form>);
};
export default A;
"""
ATOM_B = """import React, { useState } from 'react';
const B = () => {
  const [msg, setMsg] = useState('');
  return (<div><h2>Edit Comment</h2>
    <input placeholder="Edit your comment" /><button onClick={() => setMsg('Comment updated successfully')}>Edit</button>
    {msg && <p>{msg}</p>}
  </div>);
};
export default B;
"""
TEST = """import App from './a_b';
test('a1', async () => { screen.getByLabelText(/canonical url/i); screen.getByText(/save/i); screen.getByText(/updated successfully/i); });
test('a2', async () => { screen.getByLabelText(/canonical url/i); screen.getByText(/save/i); });
test('b1', async () => { screen.getByPlaceholderText(/Edit your comment/i); screen.getByText(/Edit/i); screen.getByText('Comment updated successfully'); });
test('b2', async () => { screen.getByPlaceholderText(/Edit your comment/i); screen.getByText(/Edit/i); });
"""
DUO = {'name': 'a_b', 'module': 'a_b', 'category': 'x', 'atoms': ['a', 'b']}
LIB = {'a': [{'variant': 'v1', 'code': ATOM_A, 'sha256': compiler.sha256(ATOM_A), 'verified': True, 'origin': 'm1'}],
       'b': [{'variant': 'v1', 'code': ATOM_B, 'sha256': compiler.sha256(ATOM_B), 'verified': True, 'origin': 'm1'},
             {'variant': 'v2', 'code': ATOM_B.replace('<h2>Edit Comment</h2>', '<h2>Comments</h2>'), 'sha256': 'x', 'verified': True, 'origin': 'm2'}]}


def test_selectors_split_by_half():
    by_atom = compiler.selectors_by_atom(TEST, ['a', 'b'])
    assert [s.query for s in by_atom['a']] == ['LabelText', 'Text', 'Text', 'LabelText', 'Text']
    assert any(s.exact == 'Comment updated successfully' for s in by_atom['b'])


def test_static_texts_and_dynamic_strings():
    info = compiler.analyze(ATOM_B)
    assert {(s['kind'], s['value']) for s in info['static']} >= {('text', 'Edit Comment'), ('attr:placeholder', 'Edit your comment'), ('text', 'Edit')}
    assert 'Comment updated successfully' in info['dynamic']
    assert info['code'] == ATOM_B


def test_collision_is_a_compile_error_and_relabel_resolves_it():
    plan = compiler.plan_template(DUO, LIB)
    with pytest.raises(ValueError) as error:   # b's /Edit/i also matches a's static heading "Edit Post Settings"
        compiler.compile_plan(plan, DUO, LIB, TEST)
    assert 'cross-atom selector collision' in str(error.value) and "'Edit Post Settings'" in str(error.value)
    fixed = {**plan, 'relabel': [{'atom': 'a', 'from': 'Edit Post Settings', 'to': 'Post Settings'}]}
    out = compiler.compile_plan(fixed, DUO, LIB, TEST)
    assert '<h2>Post Settings</h2>' in out['files']['atoms/a__v1.js']
    assert out['files']['atoms/a__v1.js'].replace('Post Settings', 'Edit Post Settings', 1) == ATOM_A
    # a's /updated successfully/i could match b's runtime message: reported as a warning, not an error
    assert any("'Comment updated successfully'" in w for w in out['warnings'])


def test_unchecked_plan_skips_collision_check():
    bad = {'select': {'a': 'v1', 'b': 'v1'}, 'order': ['b', 'a'], 'relabel': []}
    out = compiler.compile_plan(bad, DUO, LIB, TEST, checked=False)   # collides, but unchecked arm stitches anyway
    assert set(out['files']) == {'atoms/a__v1.js', 'atoms/b__v1.js', 'a_b.js'}
    assert out['files']['a_b.js'].index('b__v1') < out['files']['a_b.js'].index('a__v1')


def test_relabel_splices_only_the_literal_and_rejects_own_selector_text():
    plan = {'select': {'a': 'v1', 'b': 'v1'}, 'order': ['a', 'b'], 'relabel': [{'atom': 'a', 'from': 'Enter URL', 'to': 'Type a URL'}]}
    out = compiler.compile_plan(plan, DUO, LIB, TEST, checked=False)
    assert out['files']['atoms/a__v1.js'] == ATOM_A.replace('"Enter URL"', '"Type a URL"')
    own = {'select': {'a': 'v1', 'b': 'v1'}, 'order': ['a', 'b'], 'relabel': [{'atom': 'a', 'from': 'Save', 'to': 'Store'}]}
    with pytest.raises(ValueError, match='own tests select it'):
        compiler.compile_plan(own, DUO, LIB, TEST)
    still_ok = {**own, 'relabel': [{'atom': 'a', 'from': 'Save', 'to': 'Save URL'},            # /save/i still matches
                                   {'atom': 'a', 'from': 'Edit Post Settings', 'to': 'Post Settings'}]}
    assert '>Save URL<' in compiler.compile_plan(still_ok, DUO, LIB, TEST)['files']['atoms/a__v1.js']
    missing = {'select': {'a': 'v1', 'b': 'v1'}, 'order': ['a', 'b'], 'relabel': [{'atom': 'a', 'from': 'Nope', 'to': 'X'}]}
    with pytest.raises(ValueError, match='no static string'):
        compiler.compile_plan(missing, DUO, LIB, TEST)


def test_structural_errors():
    with pytest.raises(ValueError, match='permutation'):
        compiler.compile_plan({'select': {'a': 'v1', 'b': 'v1'}, 'order': ['a'], 'relabel': []}, DUO, LIB, TEST)
    with pytest.raises(ValueError, match='unknown variant'):
        compiler.compile_plan({'select': {'a': 'v9', 'b': 'v1'}, 'order': ['a', 'b'], 'relabel': []}, DUO, LIB, TEST)
    with pytest.raises(ValueError, match='exactly these atoms'):
        compiler.compile_plan({'select': {'a': 'v1'}, 'order': ['a', 'b'], 'relabel': []}, DUO, LIB, TEST)
