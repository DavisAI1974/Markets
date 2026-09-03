from pathlib import Path

DRIVER_TEST = Path('research/kalshi/frankie_raw_mbo_benchmark/tests/test_native_replay_driver.py')
LAUNCH_TEST = Path('research/kalshi/frankie_raw_mbo_benchmark/tests/test_native_a_arm_launch.py')


def once(text: str, old: str, new: str, label: str) -> str:
    count = text.count(old)
    assert count == 1, f'{label}: expected one match, got {count}'
    return text.replace(old, new, 1)


text = DRIVER_TEST.read_text(encoding='utf-8')
text = once(
    text,
    '    emit_change_points: bool = False,\n) -> NativeReplayDriver:\n',
    '    emit_change_points: bool | None = None,\n) -> NativeReplayDriver:\n',
    'make_driver sentinel default',
)
old = '''    return NativeReplayDriver(\n        identity=identity,\n        session_rule=ExchangeSessionRule(),\n        cadence=cadence or NeverInvoke(),\n        run=run,\n        emit_change_points=emit_change_points,\n    )\n'''
new = '''    kwargs = {} if emit_change_points is None else {"emit_change_points": emit_change_points}\n    return NativeReplayDriver(\n        identity=identity,\n        session_rule=ExchangeSessionRule(),\n        cadence=cadence or NeverInvoke(),\n        run=run,\n        **kwargs,\n    )\n'''
text = once(text, old, new, 'make_driver uses production default')
text = once(
    text,
    '''    def test_unfed_it_declares_itself_rather_than_reporting_a_bare_zero(self):\n        """A zero and an absence are indistinguishable, which is the whole S119 finding."""\n        _, result = self._run(emit=False)\n        summary = self._summary(result)\n        self.assertEqual(summary["observed"], 0)\n        self.assertEqual(summary["status"], "NOT_FED_BY_THE_TRAVERSAL")\n\n    def test_the_flag_is_off_by_default_because_it_is_a_size_decision(self):\n        driver = make_driver()\n        self.assertFalse(driver.emit_change_points)\n''',
    '''    def test_opt_out_declares_the_comparison_off_rather_than_reporting_a_bare_zero(self):\n        """D83/D88: an explicit comparison-off state is not an empty measurement."""\n        _, result = self._run(emit=False)\n        summary = self._summary(result)\n        self.assertEqual(summary["observed"], 0)\n        self.assertIs(summary["enabled"], False)\n        self.assertEqual(summary["status"], "DISABLED_BY_DECLARED_COMPARISON")\n\n    def test_change_points_are_on_by_default_under_d83_d88(self):\n        driver = make_driver()\n        self.assertTrue(driver.emit_change_points)\n''',
    'driver default and disabled status tests',
)
text = once(
    text,
    '    def _drive(self, *, emit: bool):\n        driver = make_driver(total_mbo_records=self.SPAN + 1, emit_change_points=emit)\n',
    '    def _drive(self, *, emit: bool | None):\n        driver = make_driver(total_mbo_records=self.SPAN + 1, emit_change_points=emit)\n',
    'candidate fixture optional override',
)
marker = '''    def test_fed_it_fires_and_says_so(self):\n        _, summary = self._drive(emit=True)\n        points = summary["event_driven_change_points"]\n        self.assertGreater(points["observed"], 0, "wired but nothing reached it")\n        self.assertEqual(points["status"], "FED_BY_THE_TRAVERSAL")\n\n'''
insert = marker + '''    def test_default_feed_fires_without_an_opt_in_flag(self):\n        _, summary = self._drive(emit=None)\n        points = summary["event_driven_change_points"]\n        self.assertIs(points["enabled"], True)\n        self.assertGreater(points["observed"], 0, "default-on wiring reached no change point")\n        self.assertEqual(points["status"], "FED_BY_THE_TRAVERSAL")\n\n'''
text = once(text, marker, insert, 'default-on candidate fixture')
text = once(
    text,
    '''        points = summary["event_driven_change_points"]\n        self.assertEqual(points["observed"], 0)\n        self.assertEqual(points["status"], "NOT_FED_BY_THE_TRAVERSAL")\n\n    def test_feeding_change_points_does_not_change_the_verdict(self):\n''',
    '''        points = summary["event_driven_change_points"]\n        self.assertEqual(points["observed"], 0)\n        self.assertIs(points["enabled"], False)\n        self.assertEqual(points["status"], "DISABLED_BY_DECLARED_COMPARISON")\n\n    def test_feeding_change_points_does_not_change_the_verdict(self):\n''',
    'candidate opt-out status',
)
DRIVER_TEST.write_text(text, encoding='utf-8')

text = LAUNCH_TEST.read_text(encoding='utf-8')
append = '''\n\nclass ChangePointDefaultCliS122Test(unittest.TestCase):\n    @staticmethod\n    def _base_args():\n        return [\n            "--arm", "A_MEMORY", "--run-id", "task-b", "--code-commit", "cafebabe",\n            "--source", "source.dbn.zst", "--source-manifest", "manifest.json",\n            "--out-dir", "out",\n        ]\n\n    def test_launch_function_defaults_change_points_on(self):\n        import inspect\n        self.assertIs(inspect.signature(launcher.launch).parameters["emit_change_points"].default, True)\n\n    def test_cli_no_flag_keeps_change_points_on(self):\n        args = launcher.parse_args(self._base_args())\n        self.assertIs(args.emit_change_points, True)\n\n    def test_cli_flag_is_an_explicit_opt_out(self):\n        args = launcher.parse_args(self._base_args() + ["--no-change-points"])\n        self.assertIs(args.emit_change_points, False)\n'''
assert 'class ChangePointDefaultCliS122Test' not in text
LAUNCH_TEST.write_text(text + append, encoding='utf-8')
