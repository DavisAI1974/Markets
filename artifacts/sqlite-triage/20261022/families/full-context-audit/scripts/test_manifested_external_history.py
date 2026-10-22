import unittest
from collect_manifested_external_history import table_rows,canonical


class ExternalHistoryTests(unittest.TestCase):
    def test_exact_clock_and_nested_payload_preserved(self):
        p={'columns':['published_ns','event_time_ns','v','missing'],'rows':[[1697652000000000001,None,[1,2],None]]}
        _,r=next(table_rows(p));self.assertEqual(r['published_ns'],1697652000000000001)
        self.assertEqual(r['v'],[1,2]);self.assertIsNone(r['missing'])
        self.assertEqual(canonical(r),canonical(dict(reversed(list(r.items())))))

    def test_malformed_and_float_clock_rejected(self):
        for p in [{'columns':['published_ns'],'rows':[[1.5]]},{'columns':['published_ns'],'rows':[[1,2]]}]:
            with self.assertRaises(AssertionError):list(table_rows(p))

    def test_duplicate_headers_preserve_both_source_positions(self):
        p={'columns':['published_ns','event_time_ns','published_ns'],'rows':[[100,None,99]]}
        _,r=next(table_rows(p))
        self.assertEqual(r,{'published_ns':100,'event_time_ns':None,'published_ns__source_column_2':99})


if __name__=='__main__':unittest.main()
