import unittest
from dipole_book_clock_audit import select_books,book_values

class ClockTests(unittest.TestCase):
    def test_past_uses_exact_integer_stamp_and_last_equal(self):
        g=[(1000000000000000001,1,0),(1000000000000000001,2,1),(1000000001000000001,3,2)]
        self.assertEqual(select_books(g,g[0][0])[0],g[1])
        self.assertIsNone(select_books(g,g[0][0]-1)[0])
    def test_completed_second_and_opening_different_clocks(self):
        g=[(10**9+5,1,0),(2*10**9+8,2,1),(3*10**9+7,3,2)]
        self.assertEqual(select_books(g,2*10**9)[1],g[2])
        self.assertEqual(select_books(g,10**9,2)[1],g[1])
    def test_source_mid_rounding_is_independent_from_past_selection(self):
        self.assertEqual(book_values({'mid':3.067})['price_raw'],3067000000)
        self.assertEqual(book_values({'mid':None})['price_raw'],0)

if __name__=='__main__':unittest.main()
