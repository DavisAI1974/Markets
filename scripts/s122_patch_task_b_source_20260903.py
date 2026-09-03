from pathlib import Path

DRIVER = Path('research/kalshi/frankie_raw_mbo_benchmark/native_replay_driver.py')
RESPONSE = Path('research/kalshi/frankie_raw_mbo_benchmark/native_response.py')
LAUNCH = Path('research/kalshi/frankie_raw_mbo_benchmark/native_a_arm_launch.py')


def once(text: str, old: str, new: str, label: str) -> str:
    count = text.count(old)
    assert count == 1, f'{label}: expected one match, got {count}'
    return text.replace(old, new, 1)


# Driver default and explicit declaration into 4.16.
text = DRIVER.read_text(encoding='utf-8')
text = once(text, '        emit_change_points: bool = False,\n', '        emit_change_points: bool = True,\n', 'driver default')
old = '''        # 4.16's event-driven half. OFF by default because turning it on is a SIZE decision\n        # under D60 - every change point is retained on its track, so retained volume becomes\n        # (open tracks x changes) - and a size decision is declared before it is taken.\n        # Unfed, `native_response.summary` says NOT_FED_BY_THE_TRAVERSAL rather than\n        # reporting a zero that reads exactly like a real absence, which is the shape seven\n        # of S119's sixteen defects took.\n        self.emit_change_points = emit_change_points\n'''
new = '''        # 4.16's event-driven half is ON by canonical default under D83/D88: the launcher\n        # carries every lawful surface unless a declared comparison explicitly turns one off.\n        # Every change point remains retained under D60; the opt-out is therefore visible in\n        # the section summary rather than being allowed to masquerade as an observed zero.\n        self.emit_change_points = emit_change_points\n'''
text = once(text, old, new, 'driver comment')
text = once(
    text,
    '''        self.session_rule = session_rule\n        self.cadence = cadence\n        self.run = run\n''',
    '''        self.session_rule = session_rule\n        self.cadence = cadence\n        self.run = run\n        self.run.response.declare_change_point_feed(enabled=emit_change_points)\n''',
    'driver declares response feed state',
)
text = once(
    text,
    '''        Off unless `emit_change_points` is set. Under D60 every change point is RETAINED on\n        its track and travels into the lifecycle row, so the retained volume is\n        (open tracks x changes) rather than (tracks) - which is a size decision, and size\n        decisions are declared before they are taken, not discovered afterwards.\n''',
    '''        Enabled by default under D83/D88. An explicit comparison may set\n        `emit_change_points=False`; under D60 the section records that disabled state rather\n        than reporting a zero that could be mistaken for an observed absence.\n''',
    'observe docstring',
)
DRIVER.write_text(text, encoding='utf-8')


# Response section distinguishes disabled comparison from enabled/no-event and direct undeclared use.
text = RESPONSE.read_text(encoding='utf-8')
text = once(
    text,
    '''        self.change_points_observed = 0\n        self.tracks_opened = 0\n''',
    '''        self.change_points_observed = 0\n        self.change_point_feed_enabled: bool | None = None\n        self.tracks_opened = 0\n''',
    'response feed state',
)
marker = '''    def observe_change_point(self, recv_ns: int, *, values_for: Any) -> int:\n'''
method = '''    def declare_change_point_feed(self, *, enabled: bool) -> None:\n        """Record whether the traversal is feeding event-driven change points.\n\n        Direct calculator use may leave this undeclared; a traversal must declare it once so\n        an explicit comparison-off state can never be mistaken for an observed zero.\n        """\n        self.change_point_feed_enabled = bool(enabled)\n\n'''
text = once(text, marker, method + marker, 'response declaration method')
old = '''            "event_driven_change_points": {\n                "observed": self.change_points_observed,\n                "status": (\n                    "NOT_FED_BY_THE_TRAVERSAL"\n                    if self.change_points_observed == 0\n                    else "FED_BY_THE_TRAVERSAL"\n                ),\n                "rule": (\n                    "the contract requires emission at every available event-driven change "\n                    "point AND at the versioned fixed horizons; a zero here means the second "\n                    "half ran and the first half was never called"\n                ),\n            },\n'''
new = '''            "event_driven_change_points": {\n                "observed": self.change_points_observed,\n                "enabled": self.change_point_feed_enabled,\n                "status": (\n                    "DISABLED_BY_DECLARED_COMPARISON"\n                    if self.change_point_feed_enabled is False\n                    else "FED_BY_THE_TRAVERSAL"\n                    if self.change_points_observed > 0\n                    else "ENABLED_NO_CHANGE_POINTS_OBSERVED"\n                    if self.change_point_feed_enabled is True\n                    else "NOT_FED_BY_THE_TRAVERSAL"\n                ),\n                "rule": (\n                    "the canonical traversal enables event-driven change points under D83/D88; "\n                    "an explicit comparison may disable them and is named as such. Enabled with "\n                    "zero observations means no eligible event fired, not that the feed was off"\n                ),\n            },\n'''
text = once(text, old, new, 'response summary status')
RESPONSE.write_text(text, encoding='utf-8')


# Launcher default and CLI opt-out. No horizon architecture changes.
text = LAUNCH.read_text(encoding='utf-8')
text = once(text, '    emit_change_points: bool = False,\n', '    emit_change_points: bool = True,\n', 'launch default')
old = '''        # 4.16's event-driven half. Under D60 every change point is retained on its track,\n        # so retained volume becomes (open tracks x changes) rather than (tracks) - a size\n        # decision, declared before it is taken.\n        emit_change_points=emit_change_points,\n'''
new = '''        # D83/D88: canonical launch carries change points by default. An explicit declared\n        # comparison may turn them off; the section summary records that disabled state.\n        emit_change_points=emit_change_points,\n'''
text = once(text, old, new, 'launch driver comment')
old = '''    parser.add_argument(\n        "--emit-change-points",\n        action="store_true",\n        help=(\n            "feed 4.16's event-driven change points. `observe_change_point` had no caller "\n            "anywhere, so run 33605852433 emitted only the fixed horizons. Every change "\n            "point is RETAINED on its track under D60, so retained volume becomes "\n            "(open tracks x changes). Off by default because that is a size decision."\n        ),\n    )\n'''
new = '''    parser.add_argument(\n        "--no-change-points",\n        action="store_false",\n        dest="emit_change_points",\n        default=True,\n        help=(\n            "turn off 4.16 event-driven change points for a declared comparison. They are ON "\n            "by canonical default under D83/D88; disabling them is explicit and the section "\n            "records the comparison-off state rather than an empty measurement."\n        ),\n    )\n'''
text = once(text, old, new, 'CLI opt-out')
LAUNCH.write_text(text, encoding='utf-8')
