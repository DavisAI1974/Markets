"""Construct future ownership without moving any prior serial-result cohort."""
from dual_box_support import make_assignment

def assignment_preserving_prior_results(state, instances, active_jobs, serial_metrics):
    pinned={tuple(job['cohort']) for job in active_jobs}
    pinned.update(tuple(str(row[k]) for k in ['outcome','horizon_s','fold'])
                  for row in serial_metrics)
    pinned.update(tuple(t) for t in state.get('pinned_cohorts',[]))
    return make_assignment(dict(state,pinned_cohorts=[list(t) for t in sorted(pinned)]),instances)
