"""The unattended day pipeline, beginning to end (SPEC_UNATTENDED_DAILY_PIPELINE_20260916.md).

Seven idempotent stages, each gated by the receipt of the one before it, each writing ONE small
JSON receipt under runs/<DAY>/ (git is the record; no data). A failed stage stops the chain and
leaves the receipts of the stages that passed; the next dispatch resumes from the first stage
whose receipt is missing. The result-bearing stage (cycles) runs only under an explicit go
naming the day's source manifest hash; without it the chain stops there with a HOLD receipt.
Nothing here holds a credential: the AWS pair comes from the environment of the runner, and the
host reads its own credentials the way it already does.

    python day_pipeline.py --configuration pipeline.json --day 20211004 [--go <manifest_hash>] [--until <stage>]
    python day_pipeline.py --configuration pipeline.json --day 20211004 --host-stop     (the always() step)

Host stages run a script over SSM. That script must end with one line `PIPELINE_RECEIPT {json}`
carrying the gate fields listed in GATES; the orchestrator parses that line and nothing else.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import time

SCHEMA = 'FRANKIE_DAY_PIPELINE_RECEIPT_V1'
STAGES = ('stage-sources', 'host-start', 'ingest', 'schedule-prefixes', 'cycles', 'package-upload', 'snapshot-stop')
RESULT_BEARING = 'cycles'
GATES = {   # the fields the stage's receipt must carry for the next stage to run
    'stage-sources': ('manifest', 'manifest_hash', 'records'),
    'host-start': ('ssm_online',),
    'ingest': ('journal_count', 'journal_hash', 'compact_sha256'),
    'schedule-prefixes': ('prefix_count', 'prefixes_sha256'),
    'cycles': ('cycles_completed', 'cycles_total'),
    'package-upload': ('upload_manifest_sha256',),
    'snapshot-stop': ('snapshot_id', 'host_state'),
}
MARKER = 'PIPELINE_RECEIPT '


class StageRefused(RuntimeError):
    pass


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':')).encode()


def subprocess_runner(argv, *, timeout):
    """Default runner: argv -> (returncode, stdout). Never echoes the environment."""
    done = subprocess.run(argv, capture_output=True, text=True, timeout=timeout)
    return done.returncode, done.stdout + ('\nSTDERR: ' + done.stderr[-2000:] if done.stderr else '')


def receipt_line(output):
    """The host script's final PIPELINE_RECEIPT line, or the last JSON line a runner tool prints."""
    for line in reversed(output.splitlines()):
        line = line.strip()
        if line.startswith(MARKER):
            return json.loads(line[len(MARKER):])
        if line.startswith('{') and line.endswith('}'):
            try:
                return json.loads(line)
            except ValueError:
                continue
    raise StageRefused('stage produced no receipt line')


class DayPipeline:
    def __init__(self, configuration, day, *, runner=subprocess_runner, runs_root='runs', now=time.time):
        self.c, self.day, self.run, self.now = dict(configuration), str(day), runner, now
        if not self.day.isdigit() or len(self.day) != 8:
            raise ValueError('day must be YYYYMMDD')
        self.directory = Path(runs_root) / self.day
        self.python = self.c.get('python', sys.executable)

    # ---- receipts -------------------------------------------------------------------------
    def path(self, stage):
        return self.directory / f'{STAGES.index(stage):02d}-{stage}.json'

    def receipt(self, stage):
        path = self.path(stage)
        if not path.exists():
            return None
        value = json.loads(path.read_bytes())
        if value.get('schema') != SCHEMA or value.get('day') != self.day or value.get('stage') != stage:
            raise StageRefused(f'{path} is not the receipt of {stage} for {self.day}')
        return value

    def write(self, stage, gate, *, command):
        previous = STAGES[STAGES.index(stage) - 1] if STAGES.index(stage) else None
        record = dict(schema=SCHEMA, day=self.day, stage=stage, at=self.now(), gate=gate,
                      command=[str(part) for part in command],
                      previous_receipt_sha256=(hashlib.sha256(canonical(self.receipt(previous))).hexdigest()
                                               if previous else None))
        self.directory.mkdir(parents=True, exist_ok=True)
        with self.path(stage).open('xb') as handle:     # a receipt is written once; never overwritten
            handle.write(json.dumps(record, indent=1, sort_keys=True).encode() + b'\n')
        return record

    def require(self, stage):
        """The gate: the previous stage's receipt exists and carries every field its gate names."""
        index = STAGES.index(stage)
        if index == 0:
            return None
        previous = STAGES[index - 1]
        record = self.receipt(previous)
        if record is None:
            raise StageRefused(f'{stage} needs the {previous} receipt first')
        missing = [name for name in GATES[previous] if name not in record['gate']]
        if missing:
            raise StageRefused(f'{previous} receipt lacks gate fields {missing}')
        return record

    # ---- stages -----------------------------------------------------------------------------
    def _ssm(self, script_key, timeout):
        return [self.python, self.c['ssm_run'], '--instance', self.c['instance'], '--region', self.c['region'],
                '--script', self.c['host_scripts'][script_key], '--timeout', str(timeout)]

    def _ec2(self, action, *extra):
        return [self.python, self.c['ec2_host'], '--instance', self.c['instance'], '--region', self.c['region'], action, *extra]

    def commands(self):
        c = self.c
        return {
            'stage-sources': [self.python, c['stage_block_sources'], '--block', c['block'], '--days', self.day,
                              '--archive', c['archive'], '--bucket', c['bucket'],
                              '--out', str(Path(c['blocks_dir']) / f'BLOCK_{self.day}_SOURCE_MANIFEST.json')],
            'host-start': self._ec2('start'),
            'ingest': self._ssm('ingest', c.get('ingest_timeout', 6 * 3600)),
            'schedule-prefixes': self._ssm('schedule_prefixes', c.get('prefix_timeout', 2 * 3600)),
            'cycles': self._ssm('cycles', c.get('cycles_timeout', 12 * 3600)),
            'package-upload': [self.python, c['upload_restore_set'], '--bucket', c['bucket'],
                               '--prefix', f"{c['restore_prefix']}/{self.day}", '--log', str(self.directory / 'upload.log')],
            'snapshot-stop': self._ec2('snapshot', '--label', self.day),
        }

    def gate_of(self, stage, output):
        value = receipt_line(output) if stage not in ('host-start', 'snapshot-stop') else {}
        if stage == 'stage-sources':
            if value.get('status') != 'block_sources_staged':
                raise StageRefused('stage_block_sources did not report block_sources_staged')
            return dict(manifest=value['manifest'], manifest_hash=value['manifest_hash'], records=value.get('records', value.get('mbo_records')))
        if stage == 'host-start':
            if 'SSM Online' not in output:
                raise StageRefused('host did not reach SSM Online')
            return dict(ssm_online=True)
        if stage == 'snapshot-stop':
            snapshot = next((word for word in output.split() if word.startswith('snap-')), None)
            if snapshot is None or 'completed' not in output:
                raise StageRefused('snapshot did not complete')
            return dict(snapshot_id=snapshot, host_state='snapshotted')
        gate = {name: value.get(name) for name in GATES[stage]}
        if any(gate[name] is None for name in gate):
            raise StageRefused(f'{stage} receipt line lacks {[n for n in gate if gate[n] is None]}')
        if stage == 'schedule-prefixes' and gate['prefix_count'] < self.c.get('minimum_prefixes', 19):
            raise StageRefused('fewer prefixes than the day requires')
        if stage == 'cycles' and gate['cycles_completed'] != gate['cycles_total']:
            raise StageRefused('cycles incomplete; resume with the same run directory')
        return gate

    def run_stage(self, stage, *, go=None):
        if self.receipt(stage) is not None:
            return 'present'
        self.require(stage)
        if stage == RESULT_BEARING:
            expected = self.receipt('stage-sources')['gate']['manifest_hash']
            if go != expected:
                hold = self.directory / f'{STAGES.index(stage):02d}-{stage}.HOLD.json'
                hold.write_bytes(json.dumps(dict(schema=SCHEMA, day=self.day, stage=stage, status='HOLD',
                    reason='no go naming this day\'s source manifest hash; data plane only',
                    manifest_hash=expected, at=self.now()), indent=1, sort_keys=True).encode() + b'\n')
                return 'hold'
        command = self.commands()[stage]
        code, output = self.run(command, timeout=self.c.get('stage_timeout', 13 * 3600))
        if code != 0:
            raise StageRefused(f'{stage} exited {code}: {output[-1500:]}')
        self.write(stage, self.gate_of(stage, output), command=command)
        return 'done'

    def resume(self, *, go=None, until=None):
        """From the first stage without a receipt; stops at the first refusal or at HOLD."""
        outcome = {}
        for stage in STAGES:
            outcome[stage] = self.run_stage(stage, go=go)
            if outcome[stage] == 'hold' or stage == until:
                break
        return outcome

    def host_stop(self):
        """The always() step: stop the host whatever happened; the stop is its own small receipt."""
        code, output = self.run(self._ec2('stop'), timeout=1200)
        self.directory.mkdir(parents=True, exist_ok=True)
        (self.directory / 'host-stop.json').write_bytes(json.dumps(dict(schema=SCHEMA, day=self.day, stage='host-stop',
            at=self.now(), returncode=code, stopped='stopped' in output), indent=1, sort_keys=True).encode() + b'\n')
        if code != 0:
            raise StageRefused('host stop failed: ' + output[-1000:])


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--configuration', required=True)
    parser.add_argument('--day', required=True)
    parser.add_argument('--go', default=None, help="the day's source manifest hash; without it the chain stops before cycles")
    parser.add_argument('--until', default=None, choices=STAGES)
    parser.add_argument('--host-stop', action='store_true')
    parser.add_argument('--runs-root', default='runs')
    args = parser.parse_args(argv)
    configuration = json.loads(Path(args.configuration).read_bytes())
    if any(word in json.dumps(configuration).lower() for word in ('secret', 'api_key', 'password', 'token')):
        raise SystemExit('pipeline configuration must contain no credential')
    pipeline = DayPipeline(configuration, args.day, runs_root=args.runs_root)
    if args.host_stop:
        pipeline.host_stop()
        return 0
    try:
        outcome = pipeline.resume(go=args.go, until=args.until)
    except StageRefused as error:
        print(json.dumps(dict(status='stage_refused', error=str(error))), flush=True)
        return 2
    print(json.dumps(dict(status='ok', day=args.day, stages=outcome)), flush=True)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
