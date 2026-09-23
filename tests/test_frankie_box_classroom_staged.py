"""Observation pages preserve every claim; assembly never repairs teacher values."""
import unittest
from deploy.aws.box.frankie_box_classroom_staged import cursor_pages, collect_observations

class FragmentTests(unittest.TestCase):
    def test_every_cursor_is_paged_once_in_original_order(self):
        roster=list(range(301))
        pages=cursor_pages(roster,128)
        self.assertEqual([x for page in pages for x in page],roster)
        self.assertEqual(list(map(len,pages)),[128,128,45])
    def test_claim_values_are_preserved_without_teacher_repair(self):
        pages=[[dict(cursor=1,state='PRESENT',value=-99.1,explanation='own claim')],
               [dict(cursor=4,state='MISSING',value=None,explanation='absent')]]
        self.assertEqual(collect_observations(pages,[1,4]),pages[0]+pages[1])
    def test_missing_duplicate_or_reordered_claims_refuse(self):
        claim=lambda c:dict(cursor=c,state='PRESENT',value=1,explanation='own claim')
        for pages in ([[claim(1)]],[[claim(1),claim(1)]],[[claim(4),claim(1)]]):
            with self.assertRaises(ValueError):collect_observations(pages,[1,4])
    def test_roster_is_exact_and_nonempty(self):
        for roster in ([],[1,1],[True],[2,1]):
            with self.assertRaises(ValueError):cursor_pages(roster,128)
    def test_nonfinite_or_nonpresent_numeric_claim_refuses(self):
        for point in (dict(cursor=1,state='PRESENT',value=float('nan'),explanation='own claim'),
                      dict(cursor=1,state='MISSING',value=0,explanation='absent')):
            with self.assertRaises(ValueError):collect_observations([[point]],[1])
