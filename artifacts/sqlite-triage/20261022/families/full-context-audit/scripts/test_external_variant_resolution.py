import unittest
from external_variant_resolution import resolve, occurrence_identity


def variant(value,stamp,primary=None,state='PRESENT'):
    return dict(available_ns=stamp,numeric={'v':value},states={'v':state},categories={},
                primary_ordinal=primary,normalized_sha256=str((value,stamp,primary)))


class VariantResolutionTests(unittest.TestCase):
    def test_future_primary_does_not_choose_an_earlier_revision(self):
        rows=[variant(2,10),variant(3,12,primary=1)]
        self.assertEqual(resolve(rows,11)['numeric']['v'],2)
        self.assertEqual(resolve(rows,12)['numeric']['v'],3)

    def test_primary_null_is_not_filled_from_alternate(self):
        got=resolve([variant(2,10),variant(None,10,primary=1,state='SOURCE_NULL')],10)
        self.assertIsNone(got['numeric']['v'])
        self.assertEqual(got['states']['v'],'SOURCE_NULL')
        self.assertEqual(got['alternatives']['v']['finite_values'],[2])

    def test_conflicting_unranked_versions_are_not_arbitrarily_selected(self):
        got=resolve([variant(2,10),variant(3,10)],10)
        self.assertIsNone(got['numeric']['v'])
        self.assertEqual(got['states']['v'],'CONFLICTING_SOURCE_VARIANTS')
        self.assertEqual(got['alternatives']['v']['finite_values'],[2,3])

    def test_equal_stamp_primary_retains_source_order(self):
        got=resolve([variant(2,10,primary=2),variant(3,10,primary=3)],10)
        self.assertEqual(got['numeric']['v'],3)

    def test_no_prior_source_is_not_an_observed_zero(self):
        self.assertIsNone(resolve([variant(0,10)],9))

    def test_same_nanosecond_distinct_message_occurrences_stay_distinct(self):
        base=('curve.trades','instrument-scope',100,99)
        self.assertNotEqual(occurrence_identity(*base,0),occurrence_identity(*base,1))
        self.assertEqual(occurrence_identity(*base,0),occurrence_identity(*base,0))


if __name__=='__main__':unittest.main()
