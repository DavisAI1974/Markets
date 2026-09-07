"""Withdrawn serving interface; use context_session.ContextSessionRunner.

Full-prefix tensor recomputation and mandatory QSV/unbounded attention were
withdrawn by Claude's owner-approved 2026-09-07 full-evidence ruling.
Historical source remains in git at 5e93896d for provenance.
"""

class FullHistoryRunner:
    def __init__(self, *args, **kwargs):
        raise ValueError('FullHistoryRunner is withdrawn; use ContextSessionRunner with declared journal context')
