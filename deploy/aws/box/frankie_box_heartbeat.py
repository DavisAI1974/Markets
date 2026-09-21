"""Frankie's progress heartbeat from his box (Root task step 1b, box edition).

Every interval (default 300 s) and at every phase change, append one ROOT_PROGRESS_V1 object to
  (a) git: branch root/cycle-<NN>-progress, file research/kalshi/frankie_boss/runs/<day>/root/progress.jsonl, pushed
      with the token read from SSM SecureString /markets/frankie/github-token (us-east-2) into memory only;
  (b) S3: s3://<bucket>/host-deliveries/<day>/principal-response/cycle-<NN>/progress/progress-<unix>-<phase>.json,
      through the box's instance role, when the role may PutObject there (a refusal is printed once and skipped).
Phase and note are read from <session>/phase (one word) and <session>/note (one line) that Frankie's session
maintains; the request digest from <session>/request_sha256. The probe frankie_host_cycle_status.yml reads both places.
Never overwrites a key; never prints a token. Runs until <session>/done exists, then writes one last heartbeat.

    python frankie_box_heartbeat.py --session /opt/frankie-box/session --day 20211003 --cycle 00 [--interval 300] [--once]
"""
import argparse
import json
import os
import subprocess
import sys
import time
from pathlib import Path

PHASES = ('downloaded', 'verified', 'reading', 'deriving', 'classroom', 'writing', 'pushing', 'correction', 'done')
BUCKET = 'frankie-granite42-568968024170-us-east-1'
REPO = 'https://github.com/DavisAI1974/Markets.git'


def read(path, default=''):
    try:
        return Path(path).read_text(encoding='utf-8').strip().splitlines()[0]
    except Exception:
        return default


def token():
    import boto3
    try:
        return boto3.client('ssm', region_name='us-east-2').get_parameter(Name='/markets/frankie/github-token', WithDecryption=True)['Parameter']['Value']
    except Exception as error:
        code = getattr(error, 'response', {}).get('Error', {}).get('Code') or type(error).__name__
        print('git heartbeat disabled: /markets/frankie/github-token not readable:', code, flush=True)
        return None


def git(args, cwd, tok=None):
    env = dict(os.environ, HOME=os.environ.get('HOME', '/root'), GIT_TERMINAL_PROMPT='0')
    cmd = ['git']
    if tok:
        # The token lives in this process's environment only; the helper echoes it to git, never to a file or log.
        env['FRANKIE_GIT_TOKEN'] = tok
        cmd += ['-c', 'credential.helper=!f() { echo username=x-access-token; echo "password=$FRANKIE_GIT_TOKEN"; }; f']
    return subprocess.run(cmd + args, cwd=cwd, env=env, capture_output=True, text=True)


def ensure_clone(work, branch, base):
    if not (work / '.git').is_dir():
        r = git(['clone', '-q', '--depth', '1', '--branch', base, REPO, str(work)], cwd='/')
        if r.returncode:
            print('clone failed:', r.stderr[-300:], flush=True); return False
    r = git(['fetch', '-q', 'origin', branch], cwd=work)
    if r.returncode == 0:
        git(['checkout', '-q', '-B', branch, 'FETCH_HEAD'], cwd=work)
    else:
        git(['checkout', '-q', '-B', branch], cwd=work)
    return True


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--session', required=True)
    p.add_argument('--day', default='20211003')
    p.add_argument('--cycle', default='00')
    p.add_argument('--interval', type=int, default=300)
    p.add_argument('--base', default='claude/cycle-0-frankie-box-rerun-od5sxk')
    p.add_argument('--once', action='store_true')
    a = p.parse_args()
    session = Path(a.session)
    branch = f'root/cycle-{a.cycle}-progress'
    rel = f'research/kalshi/frankie_boss/runs/{a.day}/root/progress.jsonl'
    work = session / 'progress-clone'
    tok = token()
    have_git = bool(tok) and ensure_clone(work, branch, a.base)
    s3_ok = True
    import boto3
    s3 = boto3.client('s3', region_name='us-east-1')
    last_phase = None
    while True:
        if not have_git:
            # the token may be granted while the session runs (Greg's SecureString): re-read it every beat until it is there
            tok = token()
            have_git = bool(tok) and ensure_clone(work, branch, a.base)
        phase = read(session / 'phase', 'reading')
        if phase not in PHASES:
            phase = 'reading'
        now = int(time.time())
        beat = dict(schema='ROOT_PROGRESS_V1', cycle_index=a.cycle, request_sha256=read(session / 'request_sha256', ''),
                    phase=phase, at=now, note=read(session / 'note', '')[:400], host='frankie-box i-035994afa8bdf66a5')
        line = json.dumps(beat, sort_keys=True)
        if s3_ok:
            key = f'host-deliveries/{a.day}/principal-response/cycle-{a.cycle}/progress/progress-{now}-{phase}.json'
            try:
                s3.put_object(Bucket=BUCKET, Key=key, Body=line.encode(), ContentType='application/json', IfNoneMatch='*')
            except Exception as error:
                code = getattr(error, 'response', {}).get('Error', {}).get('Code') or type(error).__name__
                print('s3 heartbeat disabled:', code, flush=True); s3_ok = False
        if have_git:
            target = work / rel
            target.parent.mkdir(parents=True, exist_ok=True)
            with target.open('a', encoding='utf-8') as f:
                f.write(line + '\n')
            git(['add', rel], cwd=work)
            git(['-c', 'user.name=frankie-box', '-c', 'user.email=frankie-box@markets.local', 'commit', '-q', '-m', f'root: cycle {a.cycle} progress {phase} {now}'], cwd=work)
            r = git(['push', '-q', 'origin', f'HEAD:{branch}'], cwd=work, tok=tok)
            if r.returncode:
                print('git heartbeat push failed:', r.stderr[-200:].replace(tok, '***'), flush=True)
                # the token may have been replaced or expired in SSM while this process held the old one (2026-09-21:
                # the parameter went to version 2 under a running heartbeat): re-read it for the next beat
                tok = token() or tok
        print('heartbeat', phase, now, 's3' if s3_ok else '-', 'git' if have_git else '-', flush=True)
        last_phase = phase
        if a.once or (session / 'done').exists() and phase == 'done':
            return 0
        # wake early on a phase change
        for _ in range(a.interval):
            time.sleep(1)
            if read(session / 'phase', 'reading') != last_phase or (session / 'done').exists():
                break


if __name__ == '__main__':
    sys.exit(main())
