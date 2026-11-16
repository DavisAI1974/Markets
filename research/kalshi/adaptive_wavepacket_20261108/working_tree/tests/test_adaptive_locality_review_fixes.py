"""Tests for the fixes recorded in CCODE_INDEPENDENT_REVIEW_20261108.md (science stream).

Every test here is synthetic and bounded. Nothing is real market data and nothing
here is a scientific acceptance. Finding ids (PG-*, M-*, R-*) refer to the review.
"""
import math
import statistics
import unittest

from adaptive_locality.core import LocalityError
from adaptive_locality.information import (RawMember, RawFrame, FixedBins,
                                           derive_information)
from adaptive_locality.coupling import (discover_coupling, dipole_window_probe,
                                        cross_domain_motif, chronological_partition,
                                        CouplingResult, BalanceWindow)
from test_adaptive_locality_coupling import frame, synthetic_series


class AbstentionReasonTests(unittest.TestCase):
    """PG-2: an abstention keeps the cause, never only a status string."""

    def test_constant_operator_column_reason_survives_in_direction_result(self):
        # FIb is constant: the standardized library has a zero-variance column.
        data=tuple(frame(t,ha,1.1+0.2*math.sin(0.17*t),0.5+0.1*math.cos(0.3*t),0.7,
                         0.3+0.05*math.sin(0.2*t))
                   for t,ha in ((t,0.8+0.3*math.sin(0.11*t)) for t in range(120)))
        report=discover_coupling(data)
        for result in report["results"]:
            self.assertTrue(result.status.startswith("ABSTAIN"),result.status)
            self.assertIsInstance(result.reason,str)
            self.assertIn("constant or unidentifiable",result.reason)
        # Every CouplingResult carries a reason field, including non-abstaining ones.
        self.assertTrue(all(isinstance(r.reason,str) for r in report["results"]))

    def test_window_abstention_reason_survives_in_balance_window(self):
        data=tuple(frame(t,1.+0.01*t,1.+0.01*t,0.1,0.1,0.3) for t in range(100))
        windows=dipole_window_probe(data,window=40,stride=20)
        self.assertTrue(windows)
        for w in windows:
            self.assertEqual(w.status,"ABSTAIN_RANK_OR_NUMERIC_ARTIFACT")
            self.assertIsInstance(w.reason,str)
            self.assertNotEqual(w.reason,"")
            self.assertEqual(w.coefficients,())

    def test_ready_results_carry_an_explicit_empty_or_descriptive_reason(self):
        data=synthetic_series()
        report=discover_coupling(data)
        a_to_b=next(r for r in report["results"] if r.target=="a" and r.donor=="b")
        self.assertEqual(a_to_b.status,"CANDIDATE_ASSOCIATION_REVIEW_ONLY")
        self.assertIsInstance(a_to_b.reason,str)
        self.assertIsInstance(CouplingResult.__dataclass_fields__["reason"].default,str)
        self.assertIsInstance(BalanceWindow.__dataclass_fields__["reason"].default,str)


class ChronologicalPartitionTests(unittest.TestCase):
    """M-5: the skipped interval at the split is deliberate and now documented+tested."""

    def test_training_target_frames_and_test_feature_frames_are_disjoint(self):
        for n in (50,64,100,257,1000):
            with self.subTest(n=n):
                lag,training,testing=chronological_partition(n)
                self.assertGreaterEqual(lag,3)
                self.assertEqual(training[0],lag)
                # A training interval i consumes frames i and i+1 (the target
                # derivative). A test interval j consumes frames j and j+1.
                train_frames={i+1 for i in training}|set(training)
                test_frames={j for j in testing}|{j+1 for j in testing}
                self.assertFalse(train_frames & test_frames,
                                 "training and test frames must not overlap")
                self.assertEqual(testing[-1],n-2)
                self.assertEqual(max(training)+2,min(testing))


class NSourceMotifTests(unittest.TestCase):
    """M-6: the four-science precedent stays the default; any N named sources allowed."""

    def _report(self,source):
        data=tuple(f.__class__(**{**f.__dict__,"source_identity":source,
                                   "raw_identity":f.raw_identity+source})
                   for f in synthetic_series())
        return discover_coupling(data)

    def test_default_still_requires_the_historical_four_sciences(self):
        missing=cross_domain_motif({"physics":self._report("p")})
        self.assertEqual(missing["status"],"INCOMPLETE_DOMAIN_SET")
        self.assertEqual(missing["required"],("biology","chemistry","geology","physics"))

    def test_explicit_independent_sources_are_compared_without_promotion(self):
        reports={"nymex":self._report("nymex"),"kalshi":self._report("kalshi"),
                 "weather":self._report("weather")}
        result=cross_domain_motif(reports,required=("nymex","kalshi","weather"))
        self.assertIn(result["status"],("EXPLORATORY_MOTIF_IN_3_DOMAINS",
                                        "NO_3_DOMAIN_MOTIF"))
        self.assertFalse(result["promotable"])
        self.assertEqual(set(result["candidate_directed_pairs"]),set(reports))

    def test_shared_evidence_under_different_names_is_refused(self):
        same=self._report("same")
        result=cross_domain_motif({"x":same,"y":same},required=("x","y"))
        self.assertEqual(result["status"],"NONINDEPENDENT_DOMAIN_EVIDENCE")


class FisherProxyClosedFormTests(unittest.TestCase):
    """R-2: the proxy is a location-Fisher plug-in; for a Gaussian I = 1/sigma^2.

    Two facts are pinned together: on a well-populated support the proxy matches
    the closed form, and on a sparsely populated tail the known empty-bin
    artifact INFLATES it. The artifact is recorded, not hidden.
    """

    @staticmethod
    def _quantile_frame(count, lo, hi, step, source):
        normal=statistics.NormalDist(0.,1.)
        nbins=int(round((hi-lo)/step))
        edges=tuple(round(lo+step*i,10) for i in range(nbins+1))
        bins=FixedBins(source,"gaussian-bins",(("a",edges),("b",edges)))
        z_lo,z_hi=normal.cdf(lo),normal.cdf(hi)
        members=[]
        for i in range(count):
            value=normal.inv_cdf(z_lo+(z_hi-z_lo)*(i+0.5)/count)
            for node in ("a","b"):
                members.append(RawMember(f"g-{node}-{i}",str(i),node,value,
                                         "quantile-synthetic"))
        info=derive_information(RawFrame(1,source,tuple(members)),bins)
        return info,z_hi-z_lo

    def test_well_populated_truncated_gaussian_matches_closed_form(self):
        # Truncated N(0,1) on [-3,3]: location Fisher information over the
        # interior is integral(x^2 phi)/Z = (Z - 2*3*phi(3))/Z.
        info,Z=self._quantile_frame(40000,-3.,3.,0.1,"fisher-dense")
        self.assertEqual(info.status,"READY")
        phi3=math.exp(-4.5)/math.sqrt(2*math.pi)
        expected=(Z-6*phi3)/Z
        proxy=dict(info.fisher_proxy)["a"]
        self.assertAlmostEqual(proxy,expected,delta=0.02)

    def test_sparse_tail_bins_inflate_the_proxy_and_are_a_retained_caveat(self):
        info,_=self._quantile_frame(4000,-5.,5.,0.1,"fisher-sparse")
        self.assertEqual(info.status,"READY")
        proxy=dict(info.fisher_proxy)["a"]
        # Known plug-in artifact: isolated single-member bins next to empty
        # bins contribute 4*p/h^2 each. The value is retained as evidence of the
        # artifact, which is why gate parameter-fisher-information stays open.
        self.assertGreater(proxy,1.25)


class RegistryConflictAndPartitionTests(unittest.TestCase):
    """PG-3: a conflicting re-archive is stored, not merely refused.
    PG-4: series over the byte cap are archived losslessly in parts."""

    def _registry(self,folder):
        from adaptive_locality.research_holds import ResearchHoldRegistry
        return ResearchHoldRegistry(folder/"r.sqlite",source_identity="s",
                                    contract_identity="c")

    def test_conflicting_payload_is_archived_under_conflict_name_with_hold(self):
        import tempfile
        from pathlib import Path
        with tempfile.TemporaryDirectory() as folder:
            with self._registry(Path(folder)) as store:
                first=store.archive("evidence",({"v":1},))
                with self.assertRaises(LocalityError):
                    store.archive("evidence",({"v":2},))
                # Original untouched.
                self.assertEqual(store.read_archive("evidence")["records"],[{"v":1}])
                # Conflicting payload retained under a derived name + a hold.
                conflicts=store.conflicts("evidence")
                self.assertEqual(len(conflicts),1)
                name=conflicts[0]["archive_name"]
                self.assertTrue(name.startswith("evidence-conflict-"))
                self.assertEqual(store.read_archive(name)["records"],[{"v":2}])
                case=store.get(conflicts[0]["case_id"])
                self.assertIn("ARCHIVE_NAME_CONFLICT",case["reason"])
                self.assertEqual(case["details"]["original_archive_digest"],first)
                self.assertTrue(store.verify())
                # Identical re-submission of the conflict is idempotent.
                with self.assertRaises(LocalityError):
                    store.archive("evidence",({"v":2},))
                self.assertEqual(len(store.conflicts("evidence")),1)

    def test_partitioned_archive_round_trips_without_truncation(self):
        import tempfile
        from pathlib import Path
        from adaptive_locality.research_holds import ResearchHoldRegistry
        records=tuple({"i":i,"payload":"x"*200} for i in range(400))
        with tempfile.TemporaryDirectory() as folder:
            with ResearchHoldRegistry(Path(folder)/"p.sqlite",source_identity="s",
                                      contract_identity="c",
                                      max_archive_bytes=20_000) as store:
                with self.assertRaises(LocalityError):
                    store.archive("big",records)
                receipt=store.archive_partitioned("big",records)
                self.assertGreater(receipt["part_count"],1)
                self.assertEqual(receipt["record_count"],400)
                manifest=store.read_archive("big-manifest")["records"][0]
                self.assertEqual(manifest["kind"],"LOSSLESS_PARTITION_MANIFEST")
                self.assertEqual(manifest["part_count"],receipt["part_count"])
                recovered=store.read_partitioned("big")
                self.assertEqual(recovered,[dict(r) for r in records])
                self.assertEqual(receipt["records_dropped"],0)
                self.assertTrue(store.verify())
            with ResearchHoldRegistry(Path(folder)/"p.sqlite",source_identity="s",
                                      contract_identity="c",
                                      max_archive_bytes=20_000) as store:
                self.assertEqual(store.read_partitioned("big"),[dict(r) for r in records])


if __name__=="__main__":
    unittest.main()


class ArchiveFirstCouplingTests(unittest.TestCase):
    """PG-1: five-step and Level 2 archive raw + derived BEFORE any validation/fit."""

    def _store(self,folder,bins):
        from adaptive_locality.research_holds import ResearchHoldRegistry
        return ResearchHoldRegistry(folder/"r.sqlite",source_identity="geometry-raw",
                                    contract_identity=bins.identity())

    def test_five_step_raise_conditions_still_archive_raw_and_hold(self):
        import tempfile
        from dataclasses import replace
        from pathlib import Path
        from adaptive_locality.standalone_review import archive_first_five_step_review
        from test_adaptive_locality_geometry_validation import original_series
        raw,bins,info=original_series(90)
        unusual=replace(raw[3].samples[0],value=50.)   # out of frozen range
        out_of_range=(raw[:3]+(replace(raw[3],samples=(unusual,)+raw[3].samples[1:]),)+raw[4:])
        dup=raw[:10]+(raw[5],)+raw[10:]                # duplicate evidence ids across frames
        short=raw[:20]                                  # below min_frames=50
        cases={"out-of-range":out_of_range,"duplicate-evidence":dup,"short":short}
        with tempfile.TemporaryDirectory() as folder:
            with self._store(Path(folder),bins) as store:
                for prefix,series in cases.items():
                    with self.subTest(prefix=prefix):
                        receipt=archive_first_five_step_review(
                            series,bins,store,archive_prefix=prefix)
                        self.assertIsNone(receipt["report"])
                        self.assertEqual(receipt["original_raw_frames"],len(series))
                        self.assertEqual(len(store.read_archive(prefix+"-unmodified-raw")
                                             ["records"]),len(series))
                        self.assertEqual(len(store.read_archive(prefix+"-derived-information")
                                             ["records"]),len(series))
                        self.assertTrue(receipt["research_case_ids"])
                        reasons=[store.get(c)["reason"] for c in receipt["research_case_ids"]]
                        self.assertTrue(any("FIVE_STEP" in r or "INFORMATION_UNVERIFIED" in r
                                            for r in reasons),reasons)
                        self.assertEqual(receipt["scientific_jobs_eliminated"],0)
                self.assertTrue(store.verify())

    def test_five_step_success_archives_report_with_full_raw(self):
        import tempfile
        from pathlib import Path
        from adaptive_locality.standalone_review import archive_first_five_step_review
        from test_adaptive_locality_geometry_validation import original_series
        raw,bins,info=original_series(90)
        with tempfile.TemporaryDirectory() as folder:
            with self._store(Path(folder),bins) as store:
                receipt=archive_first_five_step_review(raw,bins,store,archive_prefix="ok")
                self.assertIsNotNone(receipt["report"])
                self.assertEqual(receipt["report"]["result_count"],2)
                self.assertIsNotNone(receipt["archive_receipt"])
                self.assertEqual(receipt["archive_receipt"]["retained_full_raw_frames"],90)
                self.assertEqual(receipt,archive_first_five_step_review(
                    raw,bins,store,archive_prefix="ok"))
                self.assertTrue(store.verify())

    def test_level2_raise_and_budget_conditions_archive_before_fit(self):
        import tempfile
        from pathlib import Path
        from adaptive_locality.standalone_review import archive_first_level2_review
        from test_adaptive_locality_geometry_validation import original_series
        raw,bins,info=original_series(160)
        with tempfile.TemporaryDirectory() as folder:
            with self._store(Path(folder),bins) as store:
                ok=archive_first_level2_review(raw,bins,store,archive_prefix="l2",
                                               window=40,stride=2)
                self.assertIsNotNone(ok["level1_windows"])
                self.assertIsNotNone(ok["report"])
                self.assertEqual(ok["archive_receipt"]["retained_full_raw_frames"],160)
                # Budget breach: windows exceed max_windows -> no fit, everything archived.
                held=archive_first_level2_review(raw,bins,store,archive_prefix="l2-budget",
                                                 window=40,stride=1,max_windows=10)
                self.assertIsNone(held["report"])
                self.assertEqual(len(store.read_archive("l2-budget-unmodified-raw")
                                     ["records"]),160)
                self.assertTrue(any("LEVEL2" in store.get(c)["reason"]
                                    for c in held["research_case_ids"]))
                # Short series: Level 1 windows cannot even be formed.
                short=archive_first_level2_review(raw[:30],bins,store,
                                                  archive_prefix="l2-short",window=40)
                self.assertIsNone(short["level1_windows"])
                self.assertEqual(len(store.read_archive("l2-short-unmodified-raw")
                                     ["records"]),30)
                self.assertTrue(store.verify())


class ConditioningDiagnosticsTests(unittest.TestCase):
    """M-1: report the full standardized singular spectrum, VIF and coefficient
    standard errors for every fit; B is translation-invariant, its variance is not."""

    @staticmethod
    def _narrow(n=160,center=2.0,width=0.1,seed=3):
        import random
        rng=random.Random(seed)
        out=[]
        for t in range(n):
            ha=center+width*math.sin(0.23*t)+0.3*width*(rng.random()-.5)
            hb=1.4+0.25*math.sin(0.17*t)+0.1*(rng.random()-.5)
            out.append(frame(t,ha,hb,0.5+0.1*math.cos(0.3*t),0.7+0.1*math.sin(0.4*t),
                             0.3+0.05*math.sin(0.2*t)))
        return tuple(out)

    def test_fit_reports_spectrum_vif_and_standard_errors(self):
        from adaptive_locality.coupling import _qr_fit, _series_rows, FULL
        data=self._narrow()
        X,y=_series_rows(data,"a","b")
        fit=_qr_fit(X[:120],y[:120],FULL)
        self.assertEqual(len(fit.singular_values),len(FULL))
        self.assertTrue(all(fit.singular_values[i]>=fit.singular_values[i+1]
                            for i in range(len(FULL)-1)))
        self.assertGreater(fit.condition_number,1.)
        self.assertEqual(len(fit.variance_inflation),len(FULL))
        self.assertIsNone(dict(fit.variance_inflation)["const"])
        # Structural Ha/Ha2 collinearity on a narrow entropy range (review 4.3).
        self.assertGreater(dict(fit.variance_inflation)["Ha2"],100.)
        self.assertEqual(len(fit.coefficient_standard_errors),len(FULL))
        self.assertTrue(all(math.isfinite(v) and v>0
                            for _,v in fit.coefficient_standard_errors))
        # The old diagonal-ratio proxy stays reported (nothing dropped).
        self.assertGreater(fit.rank_diagonal_ratio,0)

    def test_wide_range_has_small_vif(self):
        from adaptive_locality.coupling import _qr_fit, _series_rows, FULL
        data=self._narrow(center=1.5,width=1.2)
        X,y=_series_rows(data,"a","b")
        fit=_qr_fit(X[:120],y[:120],FULL)
        self.assertLess(dict(fit.variance_inflation)["Ha2"],
                        dict(_qr_fit(*[list(v) for v in
                                       (lambda X2,y2:(X2[:120],y2[:120]))(
                                           *_series_rows(self._narrow(),"a","b"))],
                                     FULL).variance_inflation)["Ha2"])

    def test_balance_is_translation_invariant_but_its_error_is_reported(self):
        from dataclasses import replace
        data=self._narrow()
        shifted=tuple(replace(f,entropy=(("a",dict(f.entropy)["a"]+0.7),
                                         ("b",dict(f.entropy)["b"]+0.7)))
                      for f in data)
        windows=dipole_window_probe(data,window=60,stride=50)
        windows2=dipole_window_probe(shifted,window=60,stride=50)
        ready=[(w,v) for w,v in zip(windows,windows2)
               if w.status=="READY_RESEARCH_ONLY" and v.status=="READY_RESEARCH_ONLY"]
        self.assertTrue(ready)
        for w,v in ready:
            self.assertAlmostEqual(w.balance,v.balance,places=6)
            self.assertIsNotNone(w.balance_standard_error)
            self.assertGreater(w.balance_standard_error,0)
        report=discover_coupling(data)
        for r in report["results"]:
            if r.dipole_balance is not None:
                self.assertIsNotNone(r.balance_standard_error)


class ReparameterizationNullTests(unittest.TestCase):
    """M-2: a slowly varying donor makes Ha^2=(HaHb)^2/Hb^2 near-exact; compare the
    fitted quadratic against that fixed algebraic curve, not only against linear."""

    def test_slow_donor_quadratic_is_held_as_reparameterization(self):
        from adaptive_locality.geometry_probe import geometric_dipole_probe
        data=tuple(frame(t,0.8+0.01*t,1.0+0.001*math.sin(0.3*t),0.3,0.4,0.1)
                   for t in range(100))
        report=geometric_dipole_probe(data,"a","b",tolerance=1e-6)
        self.assertNotIn("CONSTANT_TRAIN_DONOR_HB",report["algebraic_degeneracy_flags"])
        self.assertIn("NEAR_CONSTANT_TRAIN_DONOR_HB",report["algebraic_degeneracy_flags"])
        self.assertIsNotNone(report["algebraic_curve_holdout_sse"])
        self.assertIsNotNone(report["gain_over_algebraic_curve"])
        self.assertLess(report["train_donor_coefficient_of_variation"],1e-2)
        self.assertEqual(report["status"],"RESEARCH_HOLD")
        self.assertIn("REPARAMETERIZATION",report["reason"])
        self.assertEqual(report["frames_dropped"],0)
        self.assertIsNotNone(report["quadratic_coefficients"])

    def test_varying_donor_reports_the_control_without_forcing_a_hold(self):
        from adaptive_locality.geometry_probe import geometric_dipole_probe
        data=tuple(frame(t,0.8+0.01*t,1.0+0.4*math.sin(0.3*t),0.3,0.4,0.1)
                   for t in range(100))
        report=geometric_dipole_probe(data,"a","b")
        self.assertNotIn("NEAR_CONSTANT_TRAIN_DONOR_HB",report["algebraic_degeneracy_flags"])
        self.assertIn("algebraic_curve_holdout_sse",report)
        self.assertIn("gain_over_algebraic_curve",report)


class LagSweepTests(unittest.TestCase):
    """M-4: the single matched lag becomes one point of a reported lag profile."""

    def test_coupling_result_reports_lag_profile_and_donor_autocorrelation(self):
        data=synthetic_series()
        report=discover_coupling(data)
        r=next(x for x in report["results"] if x.target=="a" and x.donor=="b")
        self.assertIsNotNone(r.donor_lag1_autocorrelation)
        self.assertTrue(-1.<=r.donor_lag1_autocorrelation<=1.)
        self.assertGreater(r.donor_lag1_autocorrelation,0.9)   # smooth toy donor
        lags=[item["lag"] for item in r.null_gain_by_lag]
        self.assertGreaterEqual(len(lags),3)
        self.assertLessEqual(len(lags),12)
        self.assertEqual(lags,sorted(set(lags)))
        self.assertTrue(all({"lag","improvement","null_gain","training_intervals"}
                            <=set(item) for item in r.null_gain_by_lag))
        self.assertTrue(all(math.isfinite(item["null_gain"]) for item in r.null_gain_by_lag))

    def test_geometry_predictive_split_reports_lag_profile(self):
        from adaptive_locality.geometry_validation import geometric_predictive_controls
        from test_adaptive_locality_geometry_controls import candidate_series
        report=geometric_predictive_controls(candidate_series(17),"a","b")
        split=report["splits"][0]
        self.assertIsNotNone(split.donor_lag1_autocorrelation)
        self.assertGreaterEqual(len(split.past_donor_gain_by_lag),3)
        self.assertIn(report["past_lag"],[x["lag"] for x in split.past_donor_gain_by_lag])


class LogBalanceTransformTests(unittest.TestCase):
    """M-3: the original Level 2 fitted log(B); offer it as an explicit variant with
    abstention on nonpositive B, never an epsilon."""

    def test_raw_and_log_variants_are_distinct_and_both_retain_windows(self):
        from adaptive_locality.level2_coupling import discover_level2_balance_links
        from test_adaptive_locality_level2_coupling import make_windows
        windows=make_windows()
        raw=discover_level2_balance_links(windows,source_identity="s",
                                          calibration_identity="c")
        log=discover_level2_balance_links(windows,source_identity="s",
                                          calibration_identity="c",balance_transform="log")
        self.assertEqual(raw["balance_transform"],"raw")
        self.assertEqual(log["balance_transform"],"log")
        self.assertEqual(log["retained_original_windows"],windows)
        self.assertNotEqual(raw["evidence_identity"],log["evidence_identity"])
        self.assertEqual(log["original_window_count"],len(windows))

    def test_log_variant_abstains_on_nonpositive_balance_without_epsilon(self):
        from dataclasses import replace
        from adaptive_locality.level2_coupling import discover_level2_balance_links
        from test_adaptive_locality_level2_coupling import make_windows
        windows=list(make_windows())
        i=next(k for k,w in enumerate(windows) if (w.target,w.donor)==("c","d"))
        windows[i]=replace(windows[i],balance=0.0)
        log=discover_level2_balance_links(windows,source_identity="s",
                                          calibration_identity="c",balance_transform="log")
        self.assertTrue(any("LOG_TRANSFORM_UNDEFINED" in x["reason"]
                            for x in log["unresolved_research_items"]))
        self.assertTrue(all(l.status=="RESEARCH_HOLD" for l in log["links"]
                            if ("c","d") in (l.target_balance,l.donor_balance)))
        raw=discover_level2_balance_links(windows,source_identity="s",
                                          calibration_identity="c")
        self.assertFalse(any("LOG_TRANSFORM_UNDEFINED" in x["reason"]
                             for x in raw["unresolved_research_items"]))


class SegmentLinkTests(unittest.TestCase):
    """PG-5: one held window no longer silences a channel entirely; the strict
    result stays, and a side-by-side fit on the longest fully READY segment is added."""

    def test_segment_links_sit_beside_strict_holds(self):
        from dataclasses import replace
        from adaptive_locality.level2_coupling import discover_level2_balance_links
        from test_adaptive_locality_level2_coupling import make_windows
        windows=list(make_windows(120))
        k=next(i for i,w in enumerate(windows)
               if (w.target,w.donor)==("a","b") and w.end_clock==24)
        windows[k]=replace(windows[k],status="ABSTAIN_RANK_OR_NUMERIC_ARTIFACT",balance=None)
        result=discover_level2_balance_links(windows,source_identity="s",
                                             calibration_identity="c")
        strict=[l for l in result["links"] if ("a","b") in (l.target_balance,l.donor_balance)]
        self.assertTrue(all(l.status=="RESEARCH_HOLD" for l in strict))
        # Windows end at t+4, so clocks run 4..123; the held window ends at 24.
        self.assertEqual(result["segment_clocks"],(25,123,99))
        self.assertEqual(len(result["segment_links"]),len(result["links"]))
        self.assertTrue(all(l.status.startswith("SEGMENT_") for l in result["segment_links"]))
        self.assertTrue(any(l.status!="SEGMENT_RESEARCH_HOLD" for l in result["segment_links"]))
        self.assertEqual(result["retained_original_windows"],tuple(windows))

    def test_no_segment_when_nothing_was_held_or_segment_too_short(self):
        from adaptive_locality.level2_coupling import discover_level2_balance_links
        from test_adaptive_locality_level2_coupling import make_windows
        clean=discover_level2_balance_links(make_windows(),source_identity="s",
                                            calibration_identity="c")
        self.assertIsNone(clean["segment_clocks"])
        self.assertEqual(clean["segment_links"],())


class PackingBoundaryTests(unittest.TestCase):
    """N-1: the original post's mechanism, formalized: neighbor-distance differences
    define finite-volume cells; a missing neighbor IS the zero-flux boundary."""

    def test_uniform_path_recovers_heat_equation_neumann_decay(self):
        from adaptive_locality.packing_boundary import flux_domain_from_path
        from adaptive_locality.boundary_validation import checked_step
        from adaptive_locality.graph_boundary import stable_explicit_dt, total_mass
        N=40
        nodes=tuple((f"c{k}",k/N) for k in range(N+1))
        domain=flux_domain_from_path(nodes,diffusivity=1.0)
        self.assertEqual(domain.boundary,("c0",f"c{N}"))
        field={name:1.+math.cos(math.pi*x) for name,x in nodes}
        mass0=total_mass(domain,field)
        dt=0.4*stable_explicit_dt(domain)
        t=0.
        while t<0.05-1e-12:
            field=checked_step(domain,field,dt)
            t+=dt
        self.assertAlmostEqual(total_mass(domain,field),mass0,places=9)
        worst=max(abs(field[name]-(1.+math.cos(math.pi*x)*math.exp(-math.pi**2*t)))
                  for name,x in nodes)
        self.assertLess(worst,1e-2)

    def test_nonuniform_spacing_from_neighbor_distances_conserves_and_relaxes(self):
        from adaptive_locality.packing_boundary import flux_domain_from_path
        from adaptive_locality.boundary_validation import checked_step
        from adaptive_locality.graph_boundary import stable_explicit_dt, total_mass
        N=40
        nodes=tuple((f"c{k}",(k/N)**1.5) for k in range(N+1))
        domain=flux_domain_from_path(nodes,diffusivity=1.0)
        # Cell volumes come from the DIFFERENCES of neighbor distances.
        volumes=[domain.volumes[n] for n,_ in nodes]
        self.assertAlmostEqual(sum(volumes),1.0,places=12)
        self.assertLess(volumes[1],volumes[-2])
        field={name:1.+math.cos(math.pi*x) for name,x in nodes}
        mass0=total_mass(domain,field)
        dt=0.4*stable_explicit_dt(domain)
        t=0.
        while t<0.5:
            field=checked_step(domain,field,dt); t+=dt
        self.assertAlmostEqual(total_mass(domain,field),mass0,places=9)
        spread=max(field.values())-min(field.values())
        self.assertLess(spread,0.05)

    def test_packing_index_centers_become_a_path_domain(self):
        from adaptive_locality.core import Observation, MetricContract
        from adaptive_locality.advanced import PackingIndex
        from adaptive_locality.packing_boundary import path_from_centers, flux_domain_from_path
        metric=MetricContract(("x","y"),(1.,1.),(1.,1.),"v1")
        index=PackingIndex(metric,0.2)
        for i,x in enumerate((0.0,0.3,0.9,1.0,0.6)):
            obs=Observation(f"e{i}","P",{"x":x,"y":0.},i,"synthetic")
            decision=index.propose(obs)
            if decision.action=="INSERT_CENTER":
                index.admit_center(obs,decision)
        path=path_from_centers(index.centers.values(),metric,"x")
        self.assertEqual([p[0] for p in path],["e0","e1","e4","e2"])
        domain=flux_domain_from_path(path,diffusivity=0.5)
        self.assertEqual(set(domain.volumes),{"e0","e1","e4","e2"})
        self.assertEqual(domain.boundary,("e0","e2"))
        with self.assertRaises(LocalityError):
            flux_domain_from_path((("a",0.),("b",0.)),diffusivity=1.)


class MisspecifiedControlTests(unittest.TestCase):
    """T-1: generators that do NOT contain the fitted term; outcome recorded, not asserted
    into a preferred direction. The point is that the control exists and is archived."""

    @staticmethod
    def _series(kind,n=200,seed=5):
        import random
        rng=random.Random(seed)
        out=[]
        ha=1.0
        z=0.
        for t in range(n):
            z=0.9*z+0.3*(rng.random()-.5)
            if kind=="common-driver":
                hb=1.2+0.6*z+0.05*(rng.random()-.5)
                ha+=0.02*(-0.5*ha+0.8*z)
            else:
                hb=1.1+0.3*math.sin(0.17*t)+0.1*(rng.random()-.5)
                ha+=0.02*(-0.4*ha+0.9*math.tanh(3.*(hb-1.1)))
            out.append(frame(t,ha,hb,0.5+0.1*math.sin(0.11*t),0.7,0.2,source=kind))
        return tuple(out)

    def test_controls_run_and_their_outcome_is_retained_whatever_it_is(self):
        from adaptive_locality.geometry_validation import geometric_predictive_controls
        for kind in ("common-driver","misspecified"):
            with self.subTest(kind=kind):
                report=geometric_predictive_controls(self._series(kind),"a","b")
                self.assertIn(report["status"],("RESEARCH_HOLD",
                    "CONSISTENT_MULTISPLIT_ASSOCIATION_REVIEW_ONLY",
                    "NO_STABLE_ADDITIONAL_GEOMETRIC_PREDICTION"))
                self.assertEqual(report["frames_dropped"],0)
                self.assertIn("NO_CAUSAL",report["trust"])
                self.assertEqual(len(report["splits"]),3)
                # A common driver CAN produce a candidate association; that is
                # exactly why the status never says causal.
                self.assertTrue(all("CAUSAL" not in s.status or "REVIEW_ONLY" in s.status
                                    for s in report["splits"]))


class CircularShiftNullTests(unittest.TestCase):
    """Bolster: the Markets tautology-killing circular-shift null, per directed pair."""

    def test_known_coupling_ranks_above_most_shifts_and_all_shifts_are_retained(self):
        from adaptive_locality.coupling import circular_shift_null
        data=synthetic_series(n=140)
        report=circular_shift_null(data,"a","b",shifts=20)
        self.assertEqual(report["shift_count"],20)
        self.assertEqual(len(report["distribution"]),20)
        self.assertTrue(all("improvement" in d and "status" in d for d in report["distribution"]))
        self.assertIsNotNone(report["fraction_of_shifts_at_or_above_actual"])
        self.assertLess(report["fraction_of_shifts_at_or_above_actual"],0.2)
        self.assertEqual(report["shifted_results_dropped"],0)
        self.assertEqual(report["actual"].null_gain_by_lag,())   # lag profile off here

    def test_independent_channels_do_not_rank_high(self):
        from adaptive_locality.coupling import circular_shift_null
        data=synthetic_series(coupled=False,n=140)
        report=circular_shift_null(data,"a","b",shifts=20)
        frac=report["fraction_of_shifts_at_or_above_actual"]
        self.assertTrue(frac is None or frac>=0.2)
