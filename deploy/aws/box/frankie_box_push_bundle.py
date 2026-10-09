"""Push route, parent side (S10, Greg 2026-10-09): write the pack the box stages from, then the SSM parameters.

Runs in the parent's cloud session, standard library only, never touches AWS or the box. The parent uploads the
file through its AWS connector, presigns a GET, and sends deploy/aws/box/frankie_box_push_code.sh over SSM.

Why a pack and not a git bundle: the session clone is shallow, and `git bundle create` of a shallow history carries
prerequisite commits (603 MB measured on 2026-10-09) that an empty repository on the box cannot satisfy. The pack is
the old staging helper's own object set (FRANKIE_SOURCE_PACK_V1: the commit, its tree and blobs, no parents), which
index-pack takes into a fresh repository. With --base (a commit already staged on the box) only the objects that
commit's tree lacks are packed (BUNDLE_KIND=delta), so the upload is the change, not the whole tree; the box hard-links
the base checkout's packs and its clean_checkout still proves every byte.

    python3 deploy/aws/box/frankie_box_push_bundle.py build [--commit HEAD] [--base <staged sha>] [--output PATH]
        -> {"path","sha256","bytes","commit","kind","base","objects","ssm_variables"}
    BUNDLE_URL=<presigned GET> python3 deploy/aws/box/frankie_box_push_bundle.py parameters --pin PIN.json \
        [--instance i-035994afa8bdf66a5] [--timeout 900] [--output PARAMS.json]
        -> the SendCommand request (DocumentName AWS-RunShellScript, commands = literal assignments + the script)
The URL is read from the environment, never from argv, and is never printed except inside the parameters file.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile

REPO = Path(__file__).resolve().parents[3]
SCRIPT = REPO / 'deploy/aws/box/frankie_box_push_code.sh'
INSTANCE = 'i-035994afa8bdf66a5'


def git(*args, **kwargs):
    env = {k: v for k, v in os.environ.items() if not k.startswith('GIT_')}
    return subprocess.run(['git', '-C', str(REPO), *args], check=True, env=env,
                          stdout=subprocess.PIPE, stderr=subprocess.PIPE, **kwargs).stdout


def resolve(rev):
    sha = git('rev-parse', '--verify', '--quiet', rev + '^{commit}').decode().strip()
    if not re.fullmatch('[0-9a-f]{40}', sha):
        raise ValueError('%s does not resolve to a commit here' % rev)
    return sha


def objects_of(sha):
    """The commit, its tree and every tree/blob under it (no parents): the old helper's pack object set."""
    out = git('rev-list', '--objects', '--no-walk', sha).decode().split('\n')
    return {line.split(' ', 1)[0] for line in out if line}


def build(commit, base, output):
    sha = resolve(commit)
    wanted = objects_of(sha)
    base_sha = None
    if base:
        base_sha = resolve(base)
        if base_sha == sha:
            raise ValueError('base equals commit; nothing to push')
        wanted = (wanted - objects_of(base_sha)) | {sha}
    if output:
        path = Path(output)
    else:
        path = Path(tempfile.gettempdir()) / ('frankie-push-%s%s.pack' % (sha[:12], '-delta-' + base_sha[:12] if base_sha else ''))
    with path.open('xb') as stream:
        subprocess.run(['git', '-C', str(REPO), 'pack-objects', '--stdout', '-q'],
                       input=('\n'.join(sorted(wanted)) + '\n').encode('ascii'), stdout=stream, check=True)
        stream.flush(); os.fsync(stream.fileno())
    hashed = hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda: stream.read(1 << 20), b''):
            hashed.update(block)
    size = path.stat().st_size
    kind = 'delta' if base_sha else 'pack'
    variables = dict(MARKETS_SHA=sha, BUNDLE_SHA256=hashed.hexdigest(), BUNDLE_BYTES=str(size), BUNDLE_KIND=kind)
    if base_sha:
        variables['BASE_SHA'] = base_sha
    return dict(schema='FRANKIE_PUSH_PACK_V1', path=str(path), sha256=hashed.hexdigest(), bytes=size, commit=sha,
                kind=kind, base=base_sha, objects=len(wanted), ssm_variables=variables)


def parameters(pin, instance, timeout):
    url = os.environ.get('BUNDLE_URL', '')
    if not url.startswith('https://'):
        raise ValueError('BUNDLE_URL (presigned https GET) required in the environment')
    variables = dict(pin['ssm_variables'], BUNDLE_URL=url)
    lines = []
    for name, value in variables.items():   # deploy/aws/ssm_run_sh.preamble's rule: literal, refuse quote/newline
        if not re.fullmatch(r'[A-Za-z_][A-Za-z0-9_]*', name) or "'" in value or '\n' in value:
            raise ValueError('assignment %s refused (quote or newline)' % name)
        lines.append("%s='%s'\n" % (name, value))
    body = ''.join(lines) + SCRIPT.read_text()
    request = dict(InstanceIds=[instance], DocumentName='AWS-RunShellScript',
                   Parameters=dict(commands=[body], executionTimeout=[str(timeout)]),
                   TimeoutSeconds=max(timeout, 30), Comment=('Push route stage ' + pin['commit'])[:100])
    if len(json.dumps(request['Parameters']).encode()) > 48 * 1024:
        raise ValueError('SSM document parameter budget exceeded')
    return request


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest='action', required=True)
    b = sub.add_parser('build')
    b.add_argument('--commit', default='HEAD')
    b.add_argument('--base', help='a commit already staged on the box (makes a delta pack)')
    b.add_argument('--output')
    p = sub.add_parser('parameters')
    p.add_argument('--pin', required=True, help='the JSON build printed')
    p.add_argument('--instance', default=INSTANCE)
    p.add_argument('--timeout', type=int, default=900)
    p.add_argument('--output', help='write the request here (it holds the URL) instead of stdout')
    args = parser.parse_args()
    try:
        if args.action == 'build':
            print(json.dumps(build(args.commit, args.base, args.output), sort_keys=True))
        else:
            request = parameters(json.loads(Path(args.pin).read_text()), args.instance, args.timeout)
            text = json.dumps(request, sort_keys=True)
            if args.output:
                fd = os.open(args.output, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
                with os.fdopen(fd, 'w') as stream:
                    stream.write(text)
                print(json.dumps(dict(written=args.output, bytes=len(text))))
            else:
                print(text)
    except (ValueError, OSError, subprocess.CalledProcessError) as error:
        detail = getattr(error, 'stderr', None)
        print('refused: %s: %s%s' % (type(error).__name__, error, (' ' + detail.decode(errors='replace').strip()) if detail else ''),
              file=sys.stderr)
        return 1
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
