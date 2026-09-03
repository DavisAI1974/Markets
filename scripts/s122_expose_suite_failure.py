from pathlib import Path

p = Path("data/s122_task_a_runner.sh")
text = p.read_text(encoding="utf-8")
old = '''python3 -m pytest research/kalshi/frankie_raw_mbo_benchmark/tests -q -p no:cacheprovider \\
  > data/suite.log 2>&1
echo "EXIT $?"
tail -2 data/suite.log
'''
new = '''set +e
python3 -m pytest research/kalshi/frankie_raw_mbo_benchmark/tests -q -p no:cacheprovider \\
  > data/suite.log 2>&1
SUITE_EXIT=$?
set -e
echo "EXIT $SUITE_EXIT"
tail -80 data/suite.log
test "$SUITE_EXIT" -eq 0
'''
assert text.count(old) == 1
p.write_text(text.replace(old, new, 1), encoding="utf-8")
