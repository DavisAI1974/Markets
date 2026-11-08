"""Agnostic five-step coupling experiment: independent synthetic controls only."""
from __future__ import annotations
import math
import unittest
from dataclasses import replace

from adaptive_locality.core import LocalityError, _digest
from adaptive_locality.information import (RawMember,RawFrame,FixedBins,InfoFrame,
                                           derive_information,validate_series)
from adaptive_locality.coupling import (discover_coupling,dipole_window_probe,
                                        cross_domain_motif,FULL)


def sample(clock, node, member, value):
    return RawMember(f"ev-{clock}-{node}-{member}",member,node,value,
                     "original-synthetic",order_id=f"order-{member}",
                     direction="AB" if node=="a" else "BA")


def frame(t, ha, hb, fia, fib, mi, source="source"):
    return InfoFrame(t,source,"fixed-calibration",_digest({"rawclock":t}),
                     (f"event-{t}-a",f"event-{t}-b"),2,
                     (("a",ha),("b",hb)),(("a",fia),("b",fib)),
                     (("a","b",mi),),"READY",())


def synthetic_series(*,coupled=True,n=160):
    """Known synthetic directional response; not a science finding."""
    records=[]
    ha=0.8
    for t in range(n):
        hb=1.1+0.23*math.sin(0.17*t)+0.11*math.sin(0.43*t)
        fia=0.9+0.12*math.cos(0.28*t)
        fib=0.7+0.13*math.sin(0.19*t)
        mi=0.35+0.07*math.sin(0.37*t)+0.05*math.cos(0.11*t)
        records.append(frame(t,ha,hb,fia,fib,mi))
        # True driver is explicit for a toy test. The library is still
        # inferred without any hard-coded topology or science labels.
        delta=-0.12*ha-0.20*ha*ha+0.12*fia
        if coupled:
            delta+=0.25*hb+0.05*hb*hb+0.70*ha*hb+0.04*mi+0.03*fib
        ha+=0.03*delta
        if not math.isfinite(ha):
            raise AssertionError("bad toy generator")
    return tuple(records)


class CouplingResearchTests(unittest.TestCase):
    def test_information_retains_every_original_event(self):
        bins=FixedBins("source","frozen-v1",
                       (("a",(-2.,-1.,0.,1.,2.)),
                        ("b",(-2.,-1.,0.,1.,2.))))
        values=[(-1.5,-1.5),(-0.5,-0.5),(0.5,0.5),(1.5,1.5)]
        raw=RawFrame(1,"source",tuple(sample(1,node,str(i),v)
                        for i,pair in enumerate(values)
                        for node,v in zip(("a","b"),pair)))
        recorded=derive_information(raw,bins)
        self.assertEqual(recorded.status,"READY")
        self.assertEqual(recorded.raw_count,8)
        self.assertEqual(set(recorded.raw_evidence_ids),
                         {s.evidence_id for s in raw.samples})
        self.assertEqual(recorded.raw_identity,raw.identity())
        self.assertAlmostEqual(dict(recorded.entropy)["a"],math.log(4))
        self.assertAlmostEqual(recorded.mi[0][2],math.log(4))
        self.assertGreaterEqual(dict(recorded.fisher_proxy)["a"],0)
        self.assertIn("a",dict(recorded.entropy))

    def test_out_of_range_and_missing_member_require_review_no_loss(self):
        bins=FixedBins("source","version",
                       (("a",(-2.,-1.,0.,1.,2.)),("b",(-2.,-1.,0.,1.,2.))))
        raw=RawFrame(1,"source",(sample(1,"a","m",1000.),
                                 sample(1,"b","m",1.5)))
        result=derive_information(raw,bins)
        self.assertEqual(result.status,"REVIEW_REQUIRED")
        self.assertEqual(result.raw_count,2)
        self.assertEqual(len(result.raw_evidence_ids),2)
        self.assertTrue(any("OUT_OF_FROZEN_RANGE" in s for s in result.review_reasons))
        self.assertEqual(result.entropy,())
        incomplete=RawFrame(1,"source",(sample(1,"a","a-only",0.),sample(1,"b","b-only",0.)))
        result=derive_information(incomplete,bins)
        self.assertIn("UNALIGNED_ENSEMBLE_MEMBERS",result.review_reasons)
        with self.assertRaises(LocalityError):
            validate_series((result,result))

    def test_synthetic_coupling_is_candidate_not_proof(self):
        data=synthetic_series()
        result=discover_coupling(data)
        self.assertEqual(result["result_count"],2)
        self.assertEqual(result["raw_evidence_count"],2*len(data))
        self.assertEqual(result["scientific_jobs_eliminated"],0)
        self.assertIn("ASSOCIATION_RESEARCH",result["trust"])
        self.assertEqual(result["operator_library"],FULL)
        a_to_b=next(r for r in result["results"] if r.target=="a" and r.donor=="b")
        self.assertEqual(a_to_b.status,"CANDIDATE_ASSOCIATION_REVIEW_ONLY")
        self.assertIsNotNone(a_to_b.dipole_balance)
        self.assertTrue(a_to_b.opposing_dipole_signs)
        self.assertGreater(a_to_b.improvement,0.15)
        self.assertEqual(a_to_b.scientific_jobs_eliminated,0)
        self.assertEqual(len(a_to_b.source_frames),len(data))

    def test_independent_self_only_does_not_generate_false_claim(self):
        data=synthetic_series(coupled=False)
        result=discover_coupling(data)
        self.assertEqual(result["scientific_jobs_eliminated"],0)
        a_to_b=next(r for r in result["results"] if r.target=="a" and r.donor=="b")
        self.assertNotEqual(a_to_b.status,"CANDIDATE_ASSOCIATION_REVIEW_ONLY")

    def test_collinear_operator_basis_abstains(self):
        data=tuple(frame(t,1.+0.01*t,1.+0.01*t,0.1,0.1,0.3) for t in range(150))
        r=discover_coupling(data)
        self.assertTrue(all(item.status.startswith("ABSTAIN") for item in r["results"]))

    def test_invalid_sequence_and_review_required_never_silently_skipped(self):
        data=synthetic_series()
        with self.assertRaises(LocalityError):
            discover_coupling((data[0],)+data)
        with self.assertRaises(LocalityError):
            discover_coupling(tuple(reversed(data)))
        with self.assertRaises(LocalityError):
            discover_coupling(data[:30])
        blocked=replace(data[9],status="REVIEW_REQUIRED",
                        review_reasons=("TRANSIENT_SPIKE:keep original",))
        with self.assertRaises(LocalityError):
            discover_coupling(data[:9]+(blocked,)+data[10:])
        with self.assertRaises(LocalityError):
            discover_coupling(data[:9]+(replace(data[9],source_identity="other"),)+data[10:])

    def test_level_two_balance_windows_are_individual_not_network_averages(self):
        data=synthetic_series()
        windows=dipole_window_probe(data,window=40,stride=8)
        self.assertGreater(len(windows),10)
        self.assertEqual({(w.target,w.donor) for w in windows},{("a","b"),("b","a")})
        self.assertTrue(all(len(w.source_frames)==41 for w in windows))
        self.assertEqual({w.scientific_jobs_eliminated for w in windows},{0})
        self.assertTrue(any(w.status=="READY_RESEARCH_ONLY" for w in windows))
        self.assertFalse(any("B_net" in label for w in windows
                             for label,_ in w.coefficients))

    def test_past_only_null_never_reads_future_or_wraps(self):
        from adaptive_locality.coupling import _operator_row, _series_rows
        data=synthetic_series(n=90)
        with self.assertRaises(LocalityError):
            _operator_row(data,2,"a","b",1)
        with self.assertRaises(LocalityError):
            _operator_row(data,2,"a","b",-3)
        past=_operator_row(data,20,"a","b",-5)
        self.assertAlmostEqual(past[4],dict(data[15].entropy)["b"])
        rows,targets=_series_rows(data,"a","b",-5)
        self.assertEqual(len(rows),len(data)-1-5)
        self.assertEqual(len(targets),len(rows))
        self.assertAlmostEqual(rows[0][4],dict(data[0].entropy)["b"])

    def test_cross_domain_requires_all_four_and_does_not_promote(self):
        result=discover_coupling(synthetic_series())
        missing=cross_domain_motif({"physics":result})
        self.assertEqual(missing["status"],"INCOMPLETE_DOMAIN_SET")
        reports={name:result for name in ("physics","biology","chemistry","geology")}
        complete=cross_domain_motif(reports)
        self.assertFalse(complete["promotable"])
        # Four labels pointing to the SAME scientific source are not
        # four independent replications; retain reports without promotion.
        self.assertEqual(complete["status"],"NONINDEPENDENT_DOMAIN_EVIDENCE")


if __name__=="__main__":
    unittest.main()
