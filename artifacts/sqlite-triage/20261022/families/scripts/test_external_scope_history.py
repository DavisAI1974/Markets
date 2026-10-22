import unittest
from external_scope_history import ScopeHistory, observation_rank

def row(value,rank,known=None,state='PRESENT',identity=None):
    return dict(observation_id=identity or str(rank),rank=(rank,0,0),effective_ns=rank if known is None else known,event_ns=rank,
                source_published_ns=rank,numeric={'v':value},states={'v':state},categories={},alternatives={})

class ScopeTests(unittest.TestCase):
    def test_late_old_vintage_does_not_replace_latest(self):
        h=ScopeHistory();h.add(row(10,10));h.add(row(5,5,known=20))
        s=h.snapshot();self.assertEqual(s['numeric']['current.v'],10)
        self.assertEqual(s['numeric']['previous.v'],5)
        self.assertEqual(s['numeric']['history.v.present_count'],2)
        self.assertEqual(s['numeric']['history.v.mean'],7.5)
    def test_null_current_is_not_last_present(self):
        h=ScopeHistory();h.add(row(2,1));h.add(row(None,2,state='SOURCE_NULL'))
        s=h.snapshot();self.assertIsNone(s['numeric']['current.v'])
        self.assertEqual(s['categories']['current.v.state'],'SOURCE_NULL')
        self.assertEqual(s['numeric']['history.v.last_present'],2)
        self.assertIsNone(s['numeric']['change.v.latest_minus_previous'])
    def test_equal_unordered_vintage_remains_ambiguous(self):
        h=ScopeHistory();h.add(row(2,10,identity='one'));h.add(row(3,10,identity='two'))
        s=h.snapshot();self.assertIsNone(s['numeric']['current.v'])
        self.assertEqual(s['categories']['current.v.state'],'TIED_OBSERVATION_VINTAGE_CONFLICT')
    def test_curve_uses_source_message_position_without_hash_order(self):
        self.assertEqual(observation_rank('curve.trades',100,99,0),observation_rank('curve.trades',100,98,1))
        self.assertLess(observation_rank('weather.obs_hourly',100,99,None),observation_rank('weather.obs_hourly',101,100,None))
        with self.assertRaises(ValueError):observation_rank('curve.trades',None,99,0)
    def test_known_primary_source_order_resolves_coincident_arrivals(self):
        h=ScopeHistory();a=row(2,10,identity='one');a['primary_source_ordinal']=3
        b=row(3,10,identity='two');b['primary_source_ordinal']=4
        h.add(b);h.add(a)
        self.assertEqual(h.snapshot()['numeric']['current.v'],3)
        self.assertEqual(h.snapshot()['numeric']['history.v.last_present'],3)

if __name__=='__main__':unittest.main()
