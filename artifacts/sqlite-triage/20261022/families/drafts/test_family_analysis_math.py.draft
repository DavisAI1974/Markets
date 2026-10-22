import unittest
from family_analysis_math import asof_index, endpoint, numeric_leaves

class ClockAnalysis(unittest.TestCase):
    def test_same_nanosecond_respects_cursor(self):
        keys=[(100,1),(100,4),(101,5)]
        self.assertEqual(asof_index(keys,100,3),0)
        self.assertEqual(asof_index(keys,100,4),1)
        self.assertEqual(asof_index(keys,99,99),-1)

    def test_no_backfill_and_no_post_session_flat_return(self):
        keys=[(100,1),(200,2)]
        values=[3.0,3.1]
        self.assertEqual(endpoint(keys,values,99,300),(None,None))
        self.assertEqual(endpoint(keys,values,301,300),(None,None))
        self.assertEqual(endpoint(keys,values,150,300),(3.0,50))

    def test_missing_and_unknown_fields_are_not_zero(self):
        result=numeric_leaves({'flow':None,'qty':0,'anchor_recv_ns':100,'nested':{'value':2},'orders':[1,2]})
        self.assertIsNone(result['flow'])
        self.assertEqual(result['qty'],0)
        self.assertNotIn('anchor_recv_ns',result)
        self.assertNotIn('orders',result)
        self.assertEqual(result['nested.value'],2)

if __name__=='__main__':unittest.main()
