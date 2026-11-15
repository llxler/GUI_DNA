from copy import deepcopy
import pytest
from test.interaction_union.run import merge


def test_boolean_union_is_type_strict_and_preserves_non_boolean_conflicts():
 a={'enabled':False,'nested':{'edit':True},'order':['a']};before=deepcopy(a)
 assert merge(a,{'enabled':True,'nested':{'edit':False},'order':['b','a']})=={'enabled':True,'nested':{'edit':True},'order':['a','b']}
 assert a==before
 for x,y in [(False,0),(True,1),(1,2),('a','b')]:
  with pytest.raises(ValueError):merge(x,y)
