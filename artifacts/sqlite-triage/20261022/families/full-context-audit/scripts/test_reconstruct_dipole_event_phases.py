import unittest
from reconstruct_dipole_event_phases import phases

def stages(values):return [dict(signed_flow=v) for v in values]

class PhaseTests(unittest.TestCase):
    def test_zero_is_not_an_opposite_reading(self):
        self.assertEqual(phases(stages([4,-1,0,-1,-1,-1]),1),['BIRTH','BIRTH','PERSISTENCE','PERSISTENCE','PERSISTENCE','REVERSAL'])
    def test_reversal_is_observed_at_third_opposite_not_next_stage(self):
        self.assertEqual(phases(stages([1,-2,-2,-2]),1),['BIRTH','BIRTH','BIRTH','REVERSAL'])
        with self.assertRaises(ValueError):phases(stages([1,-2,-2,-2,1]),1)
    def test_censored_path_does_not_invent_a_reversal(self):
        self.assertEqual(phases(stages([-1,-3,-1,2]),-1),['BIRTH','PERSISTENCE','PERSISTENCE','PERSISTENCE'])

if __name__=='__main__':unittest.main()
