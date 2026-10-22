import unittest
from dual_box_support import make_assignment
from retained_result_assignment import assignment_preserving_prior_results

class RetainedAssignmentTests(unittest.TestCase):
    def test_serial_cohort_cannot_be_moved_away_from_preserved_results(self):
        cohorts=[('o',str(h),str(f)) for h in range(21) for f in [2,3,4]]
        state=dict(required_jobs=[['core',list(t),'m'] for t in cohorts[:5]],
                   committed_jobs=[],unregistered_cohorts=[list(t) for t in cohorts[5:]])
        instances={'A':'i-a','B':'i-b'}
        original=make_assignment(state,instances)
        target=next(r['cohort'] for r in original['cohorts'] if r['owner']=='B')
        rows=[dict(zip(['outcome','horizon_s','fold'],target))]
        protected=assignment_preserving_prior_results(state,instances,[],rows)
        self.assertEqual(next(r['owner'] for r in protected['cohorts'] if r['cohort']==target),'A')
        self.assertEqual(len(protected['cohorts']),63)

if __name__=='__main__':unittest.main()
