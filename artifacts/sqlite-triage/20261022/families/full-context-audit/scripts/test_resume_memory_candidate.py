"""Focused recovery checks; synthetic compact files, no market calculations."""
import csv
import json
import pathlib
import tempfile
import unittest

from resume_memory_candidate import (GIB, Budget, committed, expected_models,
    job_id, preserve_attempt, reservation, retry_memory, scope_command)


def csvfile(path, rows):
    with path.open('w', newline='') as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)


class RecoveryTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = pathlib.Path(self.tmp.name)
        self.job = self.root / 'jobs' / 'example'
        self.job.mkdir(parents=True)
        self.cohort = ('absolute_mid_price_change', '1', '2')
        self.metric = dict(outcome=self.cohort[0], horizon_s='1', fold='2',
            model='zero_change', test_n='2')
        csvfile(self.job / 'model_metrics.csv', [self.metric])
        csvfile(self.job / 'model_predictions.csv', [
            dict(self.metric, sample_id=s, prediction='0.0', observed='1.0')
            for s in ['a', 'b']])

    def tearDown(self):
        self.tmp.cleanup()

    def test_commit_is_recoverable_without_coordinator_receipt(self):
        self.assertTrue(committed(self.job, 'core', self.cohort, 'zero_change'))

    def test_killed_receipt_does_not_hide_as_success(self):
        (self.job / 'job_receipt.json').write_text(json.dumps(dict(returncode=-9)))
        self.assertFalse(committed(self.job, 'core', self.cohort, 'zero_change'))

    def test_partial_or_duplicate_predictions_are_not_committed(self):
        csvfile(self.job / 'model_predictions.csv', [
            dict(self.metric, sample_id='a', prediction='0.0', observed='1.0')]*2)
        self.assertFalse(committed(self.job, 'core', self.cohort, 'zero_change'))

    def test_wrong_key_and_nonfinite_values_cannot_be_promoted(self):
        self.assertFalse(committed(self.job, 'core', self.cohort, 'training_mean'))
        csvfile(self.job / 'model_predictions.csv', [
            dict(self.metric, sample_id=s, prediction='nan', observed='1.0')
            for s in ['a', 'b']])
        self.assertFalse(committed(self.job, 'core', self.cohort, 'zero_change'))

    def test_error_csv_beats_complete_metrics(self):
        csvfile(self.job / 'model_errors.csv', [dict(detail='execution_error')])
        self.assertFalse(committed(self.job, 'core', self.cohort, 'zero_change'))

    def test_failure_attempt_preserves_every_file_and_symlink(self):
        (self.job / 'run.log').write_text('killed')
        archived = preserve_attempt(self.root, self.job, 'test-run')
        self.assertEqual((archived / 'run.log').read_text(), 'killed')
        self.assertTrue((archived / 'model_metrics.csv').exists())
        self.assertFalse(self.job.exists())

    def test_preservation_cannot_move_successful_job(self):
        (self.job / 'job_receipt.json').write_text(json.dumps(
            dict(returncode=0, metric_rows=1, error_rows=0)))
        with self.assertRaises(ValueError):
            preserve_attempt(self.root, self.job, 'test-run')

    def test_memory_budget_rejects_cpu_only_oversubscription(self):
        budget = Budget(496*GIB, 64*GIB, 33*GIB, 63)
        self.assertTrue(budget.admits(32*GIB, [], 400*GIB))
        self.assertFalse(budget.admits(32*GIB, [32*GIB]*12, 400*GIB))
        self.assertFalse(budget.admits(32*GIB, [], 80*GIB))

    def test_neural_and_preparation_reserve_more_than_baselines(self):
        info = dict(a_dims=[1000, 1000000], b_dims=[500, 1000000])
        self.assertGreater(reservation('neural', info), reservation('core', info))
        self.assertGreaterEqual(reservation('prepare', info), 96*GIB)

    def test_memory_limit_is_on_numerical_process_scope(self):
        cmd = scope_command(['julia', 'task.jl'], 32*GIB, 'family-test')
        self.assertIn('--property=MemoryMax='+str(32*GIB), cmd)
        self.assertIn('--property=MemorySwapMax=0', cmd)
        self.assertEqual(cmd[-2:], ['julia', 'task.jl'])

    def test_deferred_job_can_grow_past_24_gib(self):
        self.assertEqual(retry_memory(24*GIB, 400*GIB), 40*GIB)
        self.assertEqual(retry_memory(320*GIB, 400*GIB), 400*GIB)

    def test_task_exhausting_host_cannot_be_silently_skipped(self):
        with self.assertRaisesRegex(RuntimeError, 'larger host required'):
            retry_memory(400*GIB, 400*GIB)

    def test_fitted_metrics_without_weights_are_incomplete(self):
        self.metric['model'] = 'evotrees_depth3'
        csvfile(self.job / 'model_metrics.csv', [self.metric])
        csvfile(self.job / 'model_predictions.csv', [
            dict(self.metric, sample_id=s, prediction='0.0', observed='1.0')
            for s in ['a', 'b']])
        self.assertFalse(committed(self.job, 'core', self.cohort, 'evotrees_depth3'))

    def test_expected_model_list_retains_groups_and_original_hash(self):
        core, neural = expected_models(self.cohort, ['a', 'b'])
        self.assertIn('dropgroup:a', core)
        self.assertIn('drop_history', core)
        self.assertEqual(len(neural), 3)
        self.assertEqual(job_id(('absolute_mid_price_change','1','3'),
            'core','evotrees_depth3'),
            'absolute-mid-price-change-h1-fold3--core--5ca45823f90a')


if __name__ == '__main__':
    unittest.main()
