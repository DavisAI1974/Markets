"""New codec boundary checks only; no models, tokenization, or source replay."""
import copy
import importlib
from pathlib import Path
import sys
import types
import unittest
HERE=Path(__file__).resolve().parents[1]
package=types.ModuleType('v2_boundary')
package.__path__=[str(HERE)]
sys.modules[package.__name__]=package
v2=importlib.import_module('v2_boundary.granite_context_stacked_v2')
v1=v2.v1
class V2Boundary(unittest.TestCase):
    def test_exact_types_and_numeric_references(self):
        values=[
            [1700000000000000000+i*1000 for i in range(100)],
            [i*i*1000000000 for i in range(100)],
            [dict(a=1000000000000000+i*717,b=1000000000000000+i*717+32) for i in range(100)],
            {'typed':(None,True,1,-0.0,b'abc',float('inf'))}]
        for value in values:
            with self.subTest(kind=type(value).__name__):
                self.assertEqual(v1._exact(v2.decode(v2.encode(value))),v1._exact(value))
    def test_reject_forward_reference_dimension_and_scale(self):
        bad=[['C','L',['a'],[['P',0,['I',[1]]]]],
             ['C','L',['a','b'],[['N','L',['I',[1,2]]],['P',0,['I',[1]]]]],
             ['N','L',['A',0,True,['I',[1]]]]]
        for node in bad:
            with self.subTest(node=node),self.assertRaises(ValueError):
                v2._restore(node,v1._Budget(v1.DEFAULT_LIMITS))
    def test_expansion_is_bounded(self):
        with self.assertRaises(ValueError):
            v2._ints(['Z',0,0,['R',[[0,100]]]],v1._Budget(v1.DecodeLimits(max_expanded_nodes=5)))
if __name__=='__main__':unittest.main()
