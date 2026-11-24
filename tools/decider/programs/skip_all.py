"""The one program that ships: it takes nothing. It exists so the door can be checked, not to decide anything."""


def decide(packet):
    return {"action": "skip", "why": "no decider logic has been written yet",
            "rests_on": [packet["lines"][0]["source"]]}
