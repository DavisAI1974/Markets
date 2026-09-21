# Read-only inventory of Frankie's box (the ingest runner). Prints what is on it; writes nothing.
# Run through deploy/aws/ssm_run_sh.py (root, AWS-RunShellScript).
set -u
echo "### identity"; hostname; uname -a; cat /etc/os-release | head -2; id; date -u +%FT%TZ
echo "### cpu/mem"; nproc; grep -E "^(MemTotal|MemAvailable)" /proc/meminfo; uptime
echo "### disk"; df -h --output=source,size,used,avail,target 2>/dev/null | grep -vE "^(tmpfs|udev|overlay)"; lsblk -o NAME,SIZE,TYPE,MOUNTPOINT 2>/dev/null
echo "### instance role (IMDSv2)"
TOKEN=$(curl -s -m 2 -X PUT http://169.254.169.254/latest/api/token -H "X-aws-ec2-metadata-token-ttl-seconds: 60" || true)
curl -s -m 2 -H "X-aws-ec2-metadata-token: $TOKEN" http://169.254.169.254/latest/meta-data/iam/info 2>/dev/null | head -c 600; echo
echo "### tooling"; for t in python3 python3.13 python3.12 python3.11 python3.10 pip3 git aws docker; do printf '%-10s ' "$t"; command -v "$t" >/dev/null 2>&1 && { "$t" --version 2>&1 | head -1; } || echo "(absent)"; done
echo "### python packages (system python3)"; python3 -c "import importlib;[print(n, getattr(importlib.import_module(n),'__version__','?')) for n in ('boto3','numpy','torch','zstandard','databento_dbn','cryptography') if importlib.util.find_spec(n)]" 2>/dev/null; python3 -c "import importlib.util as u;print('absent:',[n for n in ('boto3','numpy','torch','zstandard','databento_dbn','cryptography') if not u.find_spec(n)])" 2>/dev/null
echo "### github actions runner"; ls -la /opt/actions-runner 2>/dev/null | head -20; systemctl list-units --type=service --all 2>/dev/null | grep -i "actions.runner" || echo "(no actions.runner unit)"; cat /opt/actions-runner/.runner 2>/dev/null | head -20
echo "### runner work leftovers (journal-stack-result = the compact journal if still here)"; ls -la /opt/actions-runner/_work 2>/dev/null; ls -la /opt/actions-runner/_work/_temp 2>/dev/null | head -20; ls -la /opt/actions-runner/_work/_temp/journal-stack-result 2>/dev/null; ls -la /opt/actions-runner/_work/_temp/journal-stack-input 2>/dev/null | head
echo "### markets checkouts / venvs"; ls -la /opt 2>/dev/null; ls -la /opt/markets 2>/dev/null | head; ls -d /opt/frankie* /mnt/* /home/*/Markets /var/lib/markets 2>/dev/null; for d in /opt/markets /opt/frankie; do [ -d "$d/.git" ] && git -C "$d" log --oneline -1 2>/dev/null; done
echo "### env files (names only)"; ls -la /etc/markets 2>/dev/null || echo "(no /etc/markets)"
echo "### processes (top cpu)"; ps -eo pid,ppid,pcpu,pmem,etime,comm --sort=-pcpu | head -12
echo "### ssm agent"; systemctl is-active snap.amazon-ssm-agent.amazon-ssm-agent.service amazon-ssm-agent 2>/dev/null | tr '\n' ' '; echo
echo "### done (read-only)"
