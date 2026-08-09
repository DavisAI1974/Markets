#!/usr/bin/env python3
"""Register the two blockers the S118 environment prep exposed. (S115/S118.)"""
import collections
import json
import os

REG = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "..", "OPEN_ITEMS.json")


def main():
    with open(REG, encoding="utf-8") as f:
        d = json.load(f, object_pairs_hook=collections.OrderedDict)
    have = {i["id"] for i in d["items"]}

    def add(**kw):
        if kw["id"] in have:
            print("exists", kw["id"])
            return
        d["items"].append(collections.OrderedDict(kw))
        print("added", kw["id"])

    add(id="A-79",
        title="BEDROCK IS GATED AT THE ACCOUNT LEVEL - no Claude model is invocable in any region, and only Greg can clear it",
        source="S118 environment prep for the Frankie two-group validation run",
        first_raised="S118", status="OPEN", size="XS", tier="ESSENTIAL",
        tier_why="It is the sole hard blocker on the Frankie architecture test, it is a console action "
                 "nobody but the account owner can take, and the OpenAI lane is not credentialed here "
                 "either - so there is currently NO reasoning backend on this host.",
        why="MEASURED S118 on account 568968024170 (arn user/Claude). `bedrock.list_foundation_models` "
            "shows 15 Claude models in us-east-1 and they are all `INFERENCE_PROFILE` only, so the bare "
            "model id cannot be invoked - the call must use the `us.` profile id. With the correct "
            "profile id, EVERY modern Claude model fails, in us-east-1, us-east-2 AND us-west-2, 15 of "
            "15 attempts, with this VERBATIM error:\n\n"
            "  ResourceNotFoundException: Model use case details have not been submitted for this "
            "account. Fill out the Anthropic use case details form before using the model. If you have "
            "already filled out the form, try again in 15 minutes.\n\n"
            "A second, different error covers claude-opus-5 / opus-4-8 / opus-4-7 / sonnet-5 / fable-5: "
            "'is not available for this account' - those are not enabled at all, which is a separate "
            "question from the form.\n\n"
            "HONESTY NOTE, because it matters for how much to trust this: an earlier probe in the same "
            "session printed OK for `us.anthropic.claude-sonnet-4-6` in us-east-2 and us-west-2. That "
            "result did NOT reproduce - the identical call then failed 15 of 15 across three regions. "
            "The repeated measurement stands and the single earlier success is unexplained; it is "
            "recorded rather than quietly dropped.",
        what="Greg fills the Anthropic use-case details form in the Bedrock console for account "
             "...4170, and enables the specific models we intend to use. Then re-run the probe before "
             "the forecast run - not the forecast run itself, which spends an hour discovering the "
             "same thing. ALTERNATIVE LANE: set `OPENAI_API_KEY` (creds.py resolves `MARKETS_` first, "
             "then the plain name, then ~/.config/markets/env) and use `--backend openai`, which needs "
             "no AWS change at all.",
        falsifier="One `converse` call returning a JSON object on the chosen profile id. Until that "
                  "call succeeds, the backend is not ready, regardless of what the console shows - the "
                  "error message itself warns of a 15-minute propagation delay.")

    add(id="A-80",
        title="THE S118 RUNNER SERVES ZERO PLAYS - two shape mismatches against brain_view, both failing OPEN",
        source="S118 environment prep; found by checking a preflight field rather than accepting PACKETS_CAUSAL",
        first_raised="S118", status="OPEN", size="XS", tier="ESSENTIAL",
        tier_why="It would have produced a completed, plausible-looking Frankie-vs-blind comparison "
                 "that actually measured **Frankie with NO PLAYS against a blind that had all 90**. "
                 "Not a wrong number - a wrong experiment, and one whose own preflight says PASS.",
        why="MEASURED S118 at head 3a72fee on `chatgpt/agent-frankie-s117`. "
            "`frankie_group_forecast_s118.preflight_group` reports `served_plays: 0` on ALL 20 days of "
            "g18 and g19 while the verdict reads `PACKETS_CAUSAL`. Cause is `_compact_brain`, and it is "
            "TWO independent shape assumptions, each wrong, each failing open to 'serve nothing' rather "
            "than raising:\n\n"
            "1. `play_index` is assumed to be `{name: row}` or `[row, ...]`. `brain_view` emits "
            "`{_note, n_plays, evaluability, rows: [...90 rows...]}`, so `index.items()` iterates FOUR "
            "METADATA KEYS and `_index_status` reads the `_note` prose as a status. Nothing matches "
            "ARMED/EVALUABLE, so `chosen` is empty.\n"
            "2. Even with the index read correctly, `selected = {name: plays[name] for name in chosen "
            "if name in plays}` assumes `view['plays']` is a MAPPING. It is a LIST of 90 play objects, "
            "so `name in plays` is a membership test of a string against dicts - always False - and "
            "`plays[name]` would raise TypeError if it were ever reached.\n\n"
            "MEASURED CORRECT ANSWER: the 90 index rows carry evaluability EVALUABLE 30, "
            "PARTIALLY_EVALUABLE 1, NO_PARSED_CONDITIONS 57, INPUT_ABSENT 2 - so **31 plays should be "
            "served**, not 0.\n\n"
            "This is an INTEGRATION defect between two branches, not a fault in either alone: the "
            "`play_index` section was added to `brain_view` at S115 on trunk, and the S118 consumer was "
            "written against a different assumed shape. It is exactly what A-70 exists to catch.",
        what="ChatGPT's fix, in their file - do not patch it here (the S118 remit is environment prep, "
             "and D8's spirit applies to their build too): read `play_index['rows']` when present, and "
             "index `view['plays']` by its `id` field rather than by mapping key. Then ASSERT a "
             "non-zero served count in the preflight, so this can never again pass as green.",
        falsifier="Preflight must report served_plays == 31 for a g18 day (30 EVALUABLE + 1 "
                  "PARTIALLY_EVALUABLE). A run whose preflight still reports 0 is not a Frankie test "
                  "and its comparison must not be scored.")

    with open(REG, "w", encoding="utf-8") as f:
        json.dump(d, f, indent=1, ensure_ascii=False)
    print("registry now %d items" % len(d["items"]))


if __name__ == "__main__":
    main()
