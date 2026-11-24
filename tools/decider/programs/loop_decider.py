"""The starting file of the loop on the decider program. It has no logic yet: it takes every signal, which is the
platform as it runs today. The loop's agents rewrite this one file; see tools/decider/programs/README.md for the
contract and tools/ratchet/programs/platform_decider.md for the loop."""


def decide(packet):
    # rests on the packet's first line only so the answer names a line that stands; the reason says there is no logic.
    return {"action": "take", "why": "no decider logic yet: the rule's own signal stands",
            "rests_on": [packet["lines"][0]["source"]]}
