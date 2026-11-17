"""Level 2 research: no hardcoded topology, rank/outlier windows held for review."""
import math
from dataclasses import replace
import unittest
from adaptive_locality.core import LocalityError, _digest
from adaptive_locality.coupling import BalanceWindow, dipole_window_probe
from adaptive_locality.level2_coupling import discover_level2_balance_links
from test_adaptive_locality_coupling import synthetic_series


def make_windows(count=120):
    channels=(("a","b"),("b","a"),("c","d"))
    values=[]
    target=1.2
    for t in range(count):
        donor=1.5+0.25*math.sin(0.17*t)+0.19*math.cos(0.37*t)
        independent=1.1+0.3*math.sin(0.14*t+0.3)+0.13*math.cos(0.23*t)
        values.append((target,donor,independent))
        target+=0.02*(-0.25*target+0.07*target*target
                       +0.65*donor-0.08*donor*donor-0.23*target*donor)
    out=[]
    for t,tuple_values in enumerate(values):
        # Individual synthetic frame identities are shared across channels;
        # the evidence for each raw window is not averaged or sampled.
        evidence=tuple(_digest({"original_frame":i}) for i in range(t,t+5))
        for (a,b),value in zip(channels,tuple_values):
            out.append(BalanceWindow(a,b,t,t+4,"READY_RESEARCH_ONLY",
                                     value,False,evidence,(),0))
    return tuple(out)


class Level2ResearchTests(unittest.TestCase):
    def test_all_channels_and_values_retained(self):
        windows=make_windows()
        result=discover_level2_balance_links(windows,
                    source_identity="synthetic",calibration_identity="fixed-bin")
        self.assertEqual(result["original_window_count"],len(windows))
        self.assertEqual(result["retained_original_windows"],windows)
        self.assertEqual(result["input_windows_dropped"],0)
        self.assertEqual(result["rank_deficiencies_dropped"],0)
        self.assertEqual(result["scientific_jobs_eliminated"],0)
        self.assertFalse(result["raw_values_averaged"])
        self.assertEqual(result["tested_link_count"],6)
        self.assertEqual(len(result["links"]),6)
        self.assertEqual(result["channels"],(("a","b"),("b","a"),("c","d")))
        self.assertTrue(any(x.status!="RESEARCH_HOLD" for x in result["links"]))
        self.assertTrue(all(x.evidence_identity==result["evidence_identity"]
                            for x in result["links"]))

    def test_rank_deficient_balance_is_held_not_discarded(self):
        windows=list(make_windows())
        windows=[replace(w,balance=1.0) if (w.target,w.donor)==("c","d") else w
                 for w in windows]
        result=discover_level2_balance_links(windows,
                    source_identity="synthetic",calibration_identity="fixed-bin")
        flagged=[r for r in result["links"] if ("c","d") in
                 (r.target_balance,r.donor_balance)]
        self.assertEqual(len(flagged),4)
        self.assertTrue(all(r.status=="RESEARCH_HOLD" for r in flagged))
        self.assertTrue(all("RANK" in r.reason or "ARTIFACT" in r.reason
                            for r in flagged))
        self.assertEqual(result["retained_original_windows"],tuple(windows))
        self.assertGreaterEqual(result["unresolved_count"],4)
        self.assertEqual(result["rank_deficiencies_dropped"],0)
        self.assertEqual(result["scientific_jobs_eliminated"],0)

    def test_missing_or_outlier_window_holds_all_evidence(self):
        windows=list(make_windows(45))
        target=next(i for i,w in enumerate(windows)
                    if w.target=="a" and w.donor=="b" and w.end_clock==24)
        windows[target]=replace(windows[target],status="ABSTAIN_RANK_OR_NUMERIC_ARTIFACT",
                                balance=None)
        result=discover_level2_balance_links(windows,
                    source_identity="synthetic",calibration_identity="fixed-bin")
        self.assertEqual(result["original_window_count"],len(windows))
        self.assertEqual(result["retained_original_windows"],tuple(windows))
        self.assertTrue(any("LEVEL1_FIT_RESEARCH_HOLD" in item["reason"]
                            for item in result["unresolved_research_items"]))
        self.assertTrue(all(x.status=="RESEARCH_HOLD" for x in result["links"]
                            if ("a","b") in (x.target_balance,x.donor_balance)))
        self.assertEqual(result["input_windows_dropped"],0)

    def test_channel_misalignment_preserved_and_failed_closed(self):
        windows=list(make_windows(45))
        windows.pop(0)
        result=discover_level2_balance_links(windows,
                    source_identity="synthetic",calibration_identity="fixed-bin")
        self.assertTrue(all(x.status=="RESEARCH_HOLD" for x in result["links"]))
        self.assertTrue(any(x["reason"]=="MISSING_WINDOWS_IN_CHANNEL"
                            for x in result["unresolved_research_items"]))
        self.assertEqual(result["retained_original_windows"],tuple(windows))

    def test_conflicting_frame_ids_stop_fit_but_retain_records(self):
        windows=list(make_windows(45))
        windows[1]=replace(windows[1],source_frames=("unrelated",))
        result=discover_level2_balance_links(windows,
                    source_identity="synthetic",calibration_identity="fixed-bin")
        self.assertTrue(all(x.status=="RESEARCH_HOLD" for x in result["links"]))
        self.assertEqual(result["original_window_count"],len(windows))
        self.assertEqual(result["retained_original_windows"],tuple(windows))

    def test_level1_windows_consume_without_loss(self):
        frames=synthetic_series(n=110)
        windows=dipole_window_probe(frames,window=40,stride=4)
        result=discover_level2_balance_links(windows,
                    source_identity=frames[0].source_identity,
                    calibration_identity=frames[0].calibration_identity)
        self.assertEqual(result["original_window_count"],len(windows))
        self.assertEqual(result["tested_link_count"],2)
        self.assertTrue(all(x.scientific_jobs_eliminated==0 for x in result["links"]))
        self.assertEqual(result["retained_original_windows"],windows)

    def test_no_silent_pair_limit_or_destructive_job(self):
        with self.assertRaises(LocalityError):
            discover_level2_balance_links(make_windows(),source_identity="s",
                    calibration_identity="c",max_channels=2)
        damaged=list(make_windows())
        damaged[0]=replace(damaged[0],scientific_jobs_eliminated=1)
        with self.assertRaises(LocalityError):
            discover_level2_balance_links(damaged,
                                          source_identity="s",calibration_identity="c")


if __name__=="__main__":
    unittest.main()
