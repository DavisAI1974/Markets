"""One HTML template for every market and transport. Only the server formats trade events."""

from decimal import Decimal
from html import escape
from pathlib import Path
from string import Template
from urllib.parse import urlencode

from .market import markets
from .rulebook import catalogue


def e(value):
    return escape(str(value), quote=True)


def card(event, profile):
    def prices(row):
        def fmt(name):
            value = row.get(name)
            return (
                "unavailable" if value is None else format(Decimal(str(value)) / profile["price_scale"], "f")
            )

        return f"bid {fmt('bid')} · ask {fmt('ask')} {e(profile['price_unit'])}"

    fields = [
        f"<strong>{e(' · '.join(str(event[k]) for k in ('rule', 'kind', 'action') if event.get(k)))}</strong>",
        f"<p>{e(event.get('reason', ''))}</p>",
    ]
    if event.get("entry"):
        fields.append(f"<small>Entry · {prices(event['entry'])} · {e(event['entry']['received'])} ns</small>")
    if "bid" in event or "ask" in event:
        fields.append(f"<small>At decision · {prices(event)}</small>")
    for field, label in [
        ("entry_rule", "Opened by"),
        ("trade_id", "Trade"),
        ("received", "Tape receive time (ns)"),
    ]:
        if event.get(field) is not None:
            fields.append(f"<small>{label} · {e(event[field])}</small>")
    return "<article>" + "".join(fields) + "</article>"


def page(market, rule, state, history=(), *, live=True):
    profiles = markets()
    profile = profiles[market]
    rules = catalogue()
    if rule and rule not in profile["rules"]:
        raise ValueError("unknown strategy for this market")

    def options(items, selected):
        return "".join(
            f'<option value="{e(k)}"' + (" selected" if k == selected else "") + f">{e(v)}</option>"
            for k, v in items
        )

    definition = (
        (
            '<details><summary>Rule definition</summary><p class="spec">'
            + e(rules[rule]["specification"])
            + "</p></details>"
        )
        if rule
        else ""
    )
    if not live and not rule:
        definition = "".join(
            "<details><summary>"
            + e(key)
            + '</summary><p class="spec">'
            + e(rules[key]["specification"])
            + "</p></details>"
            for key in profile["rules"]
        )
    history = list(history)
    query = urlencode(
        dict(
            market=market,
            rule=rule or "",
            after=history[-1]["sequence"] if history else -1,
            run=state.get("run", ""),
        )
    )
    return Template(Path(__file__).with_name("monitor.html").read_text(encoding="utf8")).substitute(
        title=e(profile["name"]),
        asset=e(profile["asset"]),
        venue=e(profile["venue"]),
        status=e(state["status"]),
        markets=options([(k, v["name"]) for k, v in profiles.items()], market),
        rules=options([("", "All strategies")] + [(k, k) for k in profile["rules"]], rule or ""),
        hide_filters="" if live else 'style="display:none"',
        definition=definition,
        cards="".join(card(row, profile) for row in reversed(history)),
        stream=e("/stream?" + query) if live else "",
    )
