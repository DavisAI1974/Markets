from pathlib import Path

p = Path("data/s122_task_a_runner.sh")
text = p.read_text(encoding="utf-8")

old = 'test "$RED_EXIT" -ne 0\ngrep -q "raw_actions" data/red.log\ntail -20 data/red.log\n'
new = 'test "$RED_EXIT" -ne 0\necho "--- RED LOG ---"\ntail -80 data/red.log\necho "--- END RED LOG ---"\ngrep -q "raw_actions" data/red.log\n'
assert text.count(old) == 1
text = text.replace(old, new, 1)

old = "removable = {'raw_actions', 'raw_actions[]'}\nfor leaf in ('source_dbn_sha256', 'source_dbn_object', 'is_snapshot', 'book_effect'):\n    if leaf in observed:\n        removable.add(f'raw_actions[].{leaf}')\n"
new = "removable = {'raw_actions', 'raw_actions[]'} | {f'raw_actions[].{leaf}' for leaf in observed}\n"
assert text.count(old) == 1
text = text.replace(old, new, 1)

old = "    if not tokens or 'raw_actions' not in tokens:\n        out.append(line)\n        continue\n    kept = [token for token in tokens if token not in removable]\n    changed += 1\n"
new = "    if not tokens or not any(token in removable for token in tokens):\n        out.append(line)\n        continue\n    kept = [token for token in tokens if token not in removable]\n    changed += 1\n"
assert text.count(old) == 1
text = text.replace(old, new, 1)

p.write_text(text, encoding="utf-8")
