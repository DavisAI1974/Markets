"""Stage 4a of the graph adoption plan: what a node and a link of the knowledge graph look like.

Plan: research/kalshi/frankie_boss/CLAUDE_ARCH_PLAN_GRAPH_ENGINEERING_ADOPTION_20261123.md, stage 4a and 4a-bis.

One register, not two (4a-bis): the Claim and Evaluation fields below carry the claim and check
contracts of Codex's research/kalshi/FRANKIE_INDEPENDENT_SCIENTIFIC_VERIFIER_PLAN.md section 5, under
their own names. Greg, 2026-11-23: no verdict or pass/fail wording unless he asks, so an Evaluation
says what was checked, what was observed and what remains open; it carries no verdict field.

Nothing here reads market data, averages, ranks or drops anything. A line that breaks a rule is
refused with the reason; it is never written in a changed form.
"""

from __future__ import annotations

SCHEMA_VERSION = "markets.kgraph.v1"

# Node types of the plan (paper list) and the Frankie entity subtypes. Order, Fill are stage 7d.
NODE_TYPES = {
    # type: (required attrs, what it is)
    "Source": (("kind", "repo", "path"), "a file, sheet or page a claim can be tied to, at one commit"),
    "Claim": (("text", "statement_kind", "inference"), "one statement, tied to its source or marked as an inference"),
    "Artifact": (("repo", "path", "version", "authoring_run"), "a made thing (code, table, document) at one version"),
    "AgentRun": (("role", "model", "task", "outcome"), "one run of an agent, with its model and tokens"),
    "Evaluation": (("rubric", "what_was_checked", "what_was_observed", "what_remains_open"),
                   "one check of a claim or artifact; no verdict word"),
    "Task": (("text", "state"), "something to do or left undone, kept even when dropped"),
    "Commit": (("repo", "sha"), "one git commit"),
    "Metric": (("name", "value", "of"), "one measured figure of one thing; never a pooled figure"),
    "Entity": (("name", "entity_kind"), "a named thing (component, rule, file family, person)"),
    "TradeDay": (("date", "starts_et", "ends_et"), "6 pm Eastern the evening before to 5 pm Eastern on the named date"),
    "DipoleEvent": (("dipole", "birth_ns", "trade_day"), "one dipole, keyed by its own id and birth time"),
    "Peak": (("trade_day", "position_on_tape"), "one peak, pinned to its place on the tape"),
    "Family": (("name",), "a family of events, as its source names it"),
    "Chain": (("name",), "a chain of events, as its source names it"),
    "CalcOutput": (("calc", "path"), "one stored output of one calculation"),
    "Render": (("path",), "one stored picture or page"),
    "Order": (("run", "order_ref"), "one intended or sent order of a paper run"),
    "Fill": (("run", "fill_ref", "price"), "one fill as the broker reported it; bid and offer beside it, never a mid"),
}

EDGE_TYPES = {
    "MENTIONS": "src names dst",
    "SUPPORTS": "src (a source, a run, a claim) is evidence for dst",
    "CONTRADICTS": "src is evidence against dst; both stay",
    "DERIVED_FROM": "src was made from dst",
    "PRODUCED": "src (a run, a commit) made dst",
    "EVALUATES": "src (an evaluation) checks dst",
    "REVISES": "src is a later wording of dst",
    "SUPERSEDES": "src is a later claim set over dst; nothing is replaced: dst stays, marked, and is called last",
    "DEPENDS_ON": "src needs dst",
    "PARENT_OF": "src is the parent of dst",
    "RESOLVED_TO": "src (a surface form) is merged into dst (the canonical entry); reversible",
    "PINNED_AT": "src is pinned to dst (a trade day, a time, a place on the tape)",
    "MEMBER_OF": "src belongs to dst",
    "FILLS": "src (a fill) fills dst (an order)",
    "PLACED_BY": "src (an order) was placed by dst (a rule version)",
}

# statement_kind is what sort of sentence the claim is in its source. It is not a grade.
STATEMENT_KINDS = (
    "decision",      # someone decided something (said_by says who)
    "measurement",   # a counted or measured figure, with its units and what it was measured on
    "state",         # where a thing stood at the time of writing (built, not built, pushed, open)
    "rule",          # a standing rule
    "open_question", # put to someone, not answered
    "slip",          # a mistake written down so it is not made again
    "plan",          # something intended, not done
    "definition",    # what a word or a thing means here
)

# Claim fields from Codex's claim registration contract (verifier plan, section 5). All optional
# here: a claim lifted from a handoff has few of them; a claim registered for a check has more.
CLAIM_CONTRACT_FIELDS = (
    "proposer", "hypothesis", "exact_claim", "scope", "boundaries", "mechanism", "alternatives",
    "code_commit", "data_manifest_hashes", "source_event_ids", "event_time", "knowledge_time",
    "outcome_visibility", "falsifiers",
)

# Evaluation fields from Codex's check register (same section). rubric is the plan's own invariant.
EVALUATION_CONTRACT_FIELDS = (
    "check_type", "method", "method_version", "claim_revision", "input_hash", "location", "scope",
    "expected_observation", "reproducibility", "exceptions", "reviewer", "required_evidence",
)

TASK_STATES = ("open", "done", "dropped", "not_extracted", "blocked")


class Refused(ValueError):
    """A line broke a write rule. The message says which rule and which line."""


def _need(attrs: dict, names, where: str) -> None:
    missing = [n for n in names if n not in attrs or attrs[n] is None or attrs[n] == ""]
    if missing:
        raise Refused(f"{where}: missing {', '.join(missing)}")


def check_node(node: dict) -> None:
    """Refuse a node line that breaks the layout or one of the four write rules of the plan."""
    for k in ("id", "type", "attrs"):
        if k not in node:
            raise Refused(f"node without {k}: {str(node)[:120]}")
    t, a, where = node["type"], node["attrs"], f"{node['type']} {node['id']}"
    if t not in NODE_TYPES:
        raise Refused(f"{where}: unknown node type")
    if not isinstance(a, dict):
        raise Refused(f"{where}: attrs is not an object")
    required = NODE_TYPES[t][0]
    if t == "Claim":
        # inference False is a real value, so it is checked on its own
        _need(a, ("text", "statement_kind"), where)
        if not isinstance(a.get("inference"), bool):
            raise Refused(f"{where}: inference must be true or false")
        if a["statement_kind"] not in STATEMENT_KINDS:
            raise Refused(f"{where}: statement_kind {a['statement_kind']!r} is not one of {STATEMENT_KINDS}")
        # write rule 1: every claim has a source or is marked as an inference
        if not a["inference"]:
            _need(a, ("source", "line_start", "line_end", "quote"), where + " (a claim that is not an inference)")
    elif t == "Metric":
        _need(a, ("name", "of"), where)
        if "value" not in a:
            raise Refused(f"{where}: missing value")
    elif t == "Fill":
        _need(a, ("run", "fill_ref"), where)
        if "price" not in a:
            raise Refused(f"{where}: missing price")
        for banned in ("mid", "mid_price", "midpoint"):
            if banned in a:
                raise Refused(f"{where}: a mid price is never stored ({banned})")
    else:
        _need(a, required, where)
    if t == "Task" and a["state"] not in TASK_STATES:
        raise Refused(f"{where}: state {a['state']!r} is not one of {TASK_STATES}")
    # write rule 2 (every artifact has an authoring run and a version) and rule 3 (every evaluation
    # names its rubric) are in the required lists above.


def check_edge(edge: dict) -> None:
    for k in ("id", "type", "src", "dst", "attrs"):
        if k not in edge:
            raise Refused(f"edge without {k}: {str(edge)[:120]}")
    if edge["type"] not in EDGE_TYPES:
        raise Refused(f"edge {edge['id']}: unknown edge type {edge['type']!r}")
    if edge["src"] == edge["dst"]:
        raise Refused(f"edge {edge['id']}: a thing is not linked to itself")
    if edge["type"] == "RESOLVED_TO":
        # a merge keeps its evidence, its confidence and the run that made it (plan 4b)
        _need(edge["attrs"], ("evidence", "confidence"), f"RESOLVED_TO {edge['id']}")
