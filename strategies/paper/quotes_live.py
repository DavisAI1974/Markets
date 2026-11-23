"""The quote runs and the trade legs, followed live (Part A). Calls root.calcs.quote_runs.QuoteRuns and
root.calcs.leg_peaks.Legs as they are; nothing of them is written again.

G1: ONE QuoteRuns that the rules read, fed only from the PRINTS' own bid and offer. A SECOND, separate QuoteRuns is
fed only from the QUOTE messages and no rule reads it; it is kept for the record.
G3: the first run of each quote and the first trade leg are cut at the start until they have ended; a fact about
them carries cut=True and a rule that reads it gets MISSING.
Every fact is a dict: the fact's own columns plus idx (the print), time_ns, place, here (set by the engine), cut.
"""
from __future__ import annotations

from typing import Optional

from root.calcs import leg_peaks, quote_runs
from strategies.paper.events import PRINT, QUOTE


def _run_facts(facts, cut_open: dict, idx: int, time_ns: int, place) -> list:
    out = []
    for f in facts:
        d = dict(zip(quote_runs.FACT_NAMES, f))
        q, kind, start = d['quote'], d['fact'], d['run_start_position']
        if kind == quote_runs.STARTED and q not in cut_open:
            cut_open[q] = start                       # the first run of this quote: cut until it ends
        cut = cut_open.get(q) == start
        if kind == quote_runs.STEP_BACK and cut:
            cut_open[q] = None                        # it has ended (the fact itself still names a cut run)
        d.update(idx=idx, time_ns=time_ns, place=place, cut=cut, here=False)
        out.append(d)
    return out


class LiveQuotes:
    def __init__(self):
        self.runs = QuoteRuns_()                       # read by the rules: the prints' own bid and offer
        self.record = QuoteRuns_()                     # QUOTE messages only; no rule reads it
        self._cut = {}
        self.at_print = []                             # (bid, offer) of every print, by print index
        self.n_print_missing = 0
        self.n_quote_messages = self.n_quote_missing = 0
        self.record_facts = []

    def on_print(self, p: PRINT, idx: int) -> tuple:
        """(facts of the runs at this print, quote_missing)."""
        self.at_print.append((p.bid, p.offer))
        if p.bid is None or p.offer is None:
            self.n_print_missing += 1
            return [], True
        _, facts = self.runs.tick(idx, p.time_ns, p.bid, p.offer)
        return _run_facts(facts, self._cut, idx, p.time_ns, p.place), False

    def on_quote(self, q: QUOTE) -> None:
        self.n_quote_messages += 1
        if q.bid is None or q.offer is None:
            self.n_quote_missing += 1
            return
        _, facts = self.record.tick(self.n_quote_messages, q.t_ns, q.bid, q.offer)
        self.record_facts.extend(facts)


def QuoteRuns_():
    return quote_runs.QuoteRuns()


class LiveLegs:
    def __init__(self):
        self.legs = leg_peaks.Legs()
        self.n_price_missing = 0

    def on_print(self, p: PRINT, idx: int) -> list:
        if p.price is None:
            self.n_price_missing += 1
            return []
        out = []
        for f in self.legs.trade(idx, p.time_ns, p.price):
            d = dict(zip(leg_peaks.LEG_FACT_NAMES, f))
            d.update(idx=idx, time_ns=p.time_ns, place=p.place, cut=d['leg_number'] == 0, here=False)
            out.append(d)
        return out
