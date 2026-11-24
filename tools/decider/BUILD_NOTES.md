# tools/decider build notes

Platform side (read 2026-11-24, `paper_platform/answers.py`, `session.py _ask_decider`):
- question.json keys: sequence, rule, side, trade_id, tape_received_ns, journal (path of the run's events.jsonl).
- answer.json keys accepted: id, action, rule, trade_id, by, packet {sha256, tokens}, asked_at_sequence, not_before_tape_ns, why.
  A take/skip needs `by` and a whole `asked_at_sequence`; `id` is optional but we write `decision-<sequence>`.

Folder life of one question: question.json -> brief.md + packet.json -> decision.json -> answer.json
(or refused.json / decision.rejected.json, answered skip). One line a question in decisions.jsonl.

- `serve` rebuilds nothing after a brief: ids and counts are kept in packet.json so a restart can still validate.
- The packet's `rests_on` ids are the `source` of each packet line (the text before the first " | ").
- A journal that cannot be read, or a signal row not in it, is refused (answered skip) rather than waited on.
- Wall time is question.json's file time to the moment this code settles; recorded only.
- Programs (`--program`): see programs/README.md. Fenced by a fresh isolated interpreter with empty env and folder; not a sandbox.
- The leak-breach check hands `serve.build_packet` a packet with a later row through that one seam (monkeypatch);
  `leakage_check` itself is untouched.
- 2026-11-24: replay_questions.py: a decider over a finished run's real opening signals, same door (serve.Server), no engine; NOT a trial (a skip changes nothing that follows); last line is counts only.
- 2026-11-24: trial_with_decider.py: one command for a platform trial with a written decider program (door + trial + decisions.jsonl copied beside the kept files); only --dry has been run, never a trial.
- 2026-11-24: file_proposer.py (MailboxFileProposer: proposed.py + answer.json, refuses what does not compile, has no decide, is identical, imports outside the standard library or names open/os/etc; a read of the code, not a sandbox); control-file field proposer.kind plan|file, default plan.
- 2026-11-24: programs/loop_decider.py (takes every signal) and ratchet/programs/platform_decider.md written; ready check run, nothing started; loop NOT run.
- 2026-11-24: tests/agent_program/test_decider_loop.py: replay over all 217 real signals of run 0f33fec4 (skip_all and loop_decider), --dry starts nothing, file proposer refusals and one loop record, control file guard; 20 passed. Checks clone no checkout of Markets (4.7G); a scratch repo holds the two real files.
- 2026-11-24: afterwards.py: the after-the-fact layer, one line for each opening signal of a journal (decision, the trade's own later rows and results, open_profit values, what the quotes did after), plus a brief section; known only afterwards, never in a packet; written, never run on a quotes file (none kept yet).
