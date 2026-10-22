import unittest
from audit_full_context_sources import Inventory,leaves,validate_context


class ContextSourceTests(unittest.TestCase):
    def test_lists_and_empty_missing_states_remain_distinct(self):
        j={'q':[{'size':1},{'size':2}],'empty':[],'null':None,'flags':{'defined':False}}
        self.assertEqual(list(leaves(j)),[('q[].size',1),('q[].size',2),('empty',[]),('null',None),('flags.defined',False)])

    def test_inventory_preserves_types_and_exact_integer_extrema(self):
        inv=Inventory();inv.add('a',{'clock':1697652000000000001,'v':[None,0,False,2.5]})
        self.assertEqual(inv.rows[('a','clock')]['maximum'],1697652000000000001)
        self.assertEqual(inv.rows[('a','v[]')]['finite'],2)
        self.assertEqual(inv.rows[('a','v[]')]['types'],{'NoneType':1,'int':1,'bool':1,'float':1})

    def test_asof_cursor_and_instrument_are_independent_requirements(self):
        c={'known_by_ns':'101','input_cursor':'10','cutoff_ns':'101'}
        s={'cursor_cap':'10','instrument_id':'7'}
        validate_context(c,s,101,10,7)
        for known,cursor,inst in [(102,10,7),(101,11,7),(101,10,8)]:
            with self.assertRaises(AssertionError):validate_context(c,s,known,cursor,inst)
        with self.assertRaises(AssertionError):validate_context(c,{**s,'cursor_cap':'9'},101,10,7)


if __name__=='__main__':unittest.main()
