"""
signal_poster.py — Discord bot for the markets-watch closed signal feed.

Subscribes to the backend's SSE stream at /api/stream and posts each signal
event to a configured Discord channel. Plain-language headlines (no math
jargon), read-quality colors, multi-embed cascade posts, and an
optional matplotlib-rendered price/volume chart attachment.

Setup:
  1. Create a Discord application at https://discord.com/developers/applications
  2. Add a bot, copy the bot token, set DISCORD_BOT_TOKEN env var
  3. Invite bot to your server with permissions: Send Messages, Embed Links,
     Read Message History, Use Slash Commands, Attach Files
  4. Set DISCORD_CHANNEL_ID env var to the channel where signals should post
  5. Set MARKETS_WATCH_API env var to your backend URL (default localhost:8000)
  6. Set MARKETS_WATCH_APP_URL env var to the mobile app URL for deep links
  7. (Optional) set SIGNAL_POSTER_ATTACH_CHART=0 to skip chart attachments

Run: python signal_poster.py
"""

from __future__ import annotations

import asyncio
import io
import json
import os
from datetime import datetime, timezone

import aiohttp
import discord
from discord import app_commands
from discord.ext import tasks


BOT_TOKEN = os.environ.get("DISCORD_BOT_TOKEN", "")
CHANNEL_ID = int(os.environ.get("DISCORD_CHANNEL_ID", "0"))
API_BASE = os.environ.get("MARKETS_WATCH_API", "http://localhost:8000")
APP_BASE_URL = os.environ.get("MARKETS_WATCH_APP_URL", "").rstrip("/")
ATTACH_CHART = os.environ.get("SIGNAL_POSTER_ATTACH_CHART", "1") not in ("0", "false", "no")
BOT_DISPLAY_NAME = os.environ.get("SIGNAL_POSTER_NAME", "markets-watch")
BOT_AVATAR_URL = os.environ.get("SIGNAL_POSTER_AVATAR_URL", "")


# Regime → (base color int, label, emoji). Color is the clean-read anchor;
# lower signal strength is shaded lighter so the stripe still hints at quality.
REGIME_STYLES = {
    "WHALE_UP":             (0x16a34a, "Whale buyer detected", "🐋"),
    "WHALE_DOWN":           (0xdc2626, "Whale seller detected", "🐋"),
    "WHALE_NASCENT_UP":     (0x10b981, "Buy pressure forming", "🐋"),
    "WHALE_NASCENT_DOWN":   (0xf43f5e, "Sell pressure forming", "🐋"),
    "HERD_UP":              (0xf97316, "Herd buying",          "🌊"),
    "HERD_DOWN":            (0xb91c1c, "Herd selling",         "🌊"),
    "EQUILIBRIUM_TWO_SIDED":(0x3b82f6, "Equilibrium",          "⚖️"),
    "WASH_PAIRED":          (0xeab308, "Suspect flow - skip",  "⚠️"),
    "WASH_HAWKES":          (0xeab308, "Suspect flow - skip",  "⚠️"),
    "DEPLETED":             (0x9ca3af, "Quiet market",         "💤"),
    "UNKNOWN":              (0x6b7280, "Watching",             "❓"),
    # Composite regimes from cross-venue cascade detection
    "CROSS_VENUE_WHALE_HERD_UP":   (0x10b981, "Cross-venue cascade ↑", "🌊"),
    "CROSS_VENUE_HERD_WHALE_UP":   (0x10b981, "Cross-venue cascade ↑", "🌊"),
    "CROSS_VENUE_WHALE_HERD_DOWN": (0xb91c1c, "Cross-venue cascade ↓", "🌊"),
    "CROSS_VENUE_HERD_WHALE_DOWN": (0xb91c1c, "Cross-venue cascade ↓", "🌊"),
}

MARKET_STRUCTURE_COPY = {
    "WHALE_UP": "Concentrated buyer: a big player is lifting offers. Piggyback early, but watch for exhaustion.",
    "WHALE_DOWN": "Concentrated seller: a big player is hitting bids. Pressure can end fast when inventory is done.",
    "WHALE_NASCENT_UP": "Early buyer pressure: forming, not confirmed. Wait for more volume or venue confirmation before sizing up.",
    "WHALE_NASCENT_DOWN": "Early seller pressure: forming, not confirmed. Wait for persistence before leaning into it.",
    "HERD_UP": "Broad crowd buying: many participants are moving together. Momentum can run, but overshoots can snap back.",
    "HERD_DOWN": "Broad crowd selling: many participants are rushing the same way. Avoid catching it until the cascade slows.",
    "EQUILIBRIUM_TWO_SIDED": "Two-sided flow: buyers and sellers are pushing back. No clear directional edge yet.",
    "WASH_PAIRED": "Artificial-looking flow: price discovery is suspect. Skip it until cleaner participation returns.",
    "WASH_HAWKES": "Artificial-looking flow: price discovery is suspect. Skip it until cleaner participation returns.",
    "DEPLETED": "Quiet market: not enough flow to trust the read. Wait for activity to return.",
    "CROSS_VENUE_WHALE_HERD_UP": "Big-player buying is spilling into crowd buying across venues. Momentum can accelerate.",
    "CROSS_VENUE_HERD_WHALE_UP": "Crowd buying and big-player buying are aligned across venues. Stronger than a single-venue read.",
    "CROSS_VENUE_WHALE_HERD_DOWN": "Big-player selling is spilling into crowd selling across venues. Watch for cascade, then exhaustion.",
    "CROSS_VENUE_HERD_WHALE_DOWN": "Crowd selling and big-player selling are aligned across venues. Avoid fighting it until pressure slows.",
}


intents = discord.Intents.default()
client = discord.Client(intents=intents)
tree = app_commands.CommandTree(client)


@client.event
async def on_ready():
    print(f"[discord-bot] logged in as {client.user}")
    await tree.sync()
    if not stream_listener.is_running():
        stream_listener.start()


# ---------------------------------------------------------------------------
# Formatting helpers
# ---------------------------------------------------------------------------


def _fmt_price(p):
    if not p:
        return "—"
    if p >= 1000:
        return f"${p:,.2f}"
    if p >= 1:
        return f"${p:.4f}"
    return f"${p:.6f}"


def _fmt_qty(q):
    if not q:
        return "0"
    if q >= 1000:
        return f"{q:,.1f}"
    if q >= 1:
        return f"{q:.3f}"
    return f"{q:.6f}"


def _shade(color: int, factor: float) -> int:
    """Linearly interpolate a 0xRRGGBB integer toward white (factor 0 = white,
    factor 1 = original). Used to wash out low-confidence stripes."""
    factor = max(0.35, min(1.0, factor))
    r = (color >> 16) & 0xff
    g = (color >> 8) & 0xff
    b = color & 0xff
    r = int(255 - (255 - r) * factor)
    g = int(255 - (255 - g) * factor)
    b = int(255 - (255 - b) * factor)
    return (r << 16) | (g << 8) | b


def _confidence_color(base_color: int, conf: float) -> int:
    """Signal strength 0–1 → shaded version of base color. <0.5 = washed out,
    >=0.7 = full saturation."""
    if conf >= 0.7:
        return base_color
    if conf >= 0.5:
        return _shade(base_color, 0.75)
    return _shade(base_color, 0.5)


def _read_quality_label(sig: dict) -> str:
    regime = sig.get("regime") or "UNKNOWN"
    if regime == "EQUILIBRIUM_TWO_SIDED":
        return "Two-sided"
    if regime == "WHALE_UP":
        return "Clean buyer"
    if regime == "WHALE_DOWN":
        return "Clean seller"
    if regime in ("WHALE_NASCENT_UP", "WHALE_NASCENT_DOWN"):
        return "Forming"
    if regime in ("HERD_UP", "HERD_DOWN"):
        return "Crowd"
    if regime.startswith("CROSS_VENUE_"):
        return "Confirmed"
    if regime.startswith("WASH"):
        return "Noisy"
    if regime == "DEPLETED":
        return "Thin"

    adjusted = sig.get("adjusted_confidence", sig.get("confidence", 0.0)) or 0.0
    if adjusted >= 0.7:
        return "Strong"
    if adjusted >= 0.45:
        return "Mixed"
    return "Incomplete"


def _app_url(path: str) -> str:
    if not APP_BASE_URL:
        return ""
    if not path.startswith("/"):
        path = "/" + path
    return f"{APP_BASE_URL}{path}"


def _signal_url(sig: dict) -> str:
    signal_id = sig.get("signal_id")
    if signal_id:
        return _app_url(f"/signal/{signal_id}")
    return _tape_url(sig)


def _tape_url(sig: dict) -> str:
    asset = sig.get("asset", "")
    venue = sig.get("venue", "")
    if not asset or not venue:
        return _app_url("/")
    return _app_url(f"/tape/{asset}/{venue}")


def _market_structure(regime: str) -> str:
    return MARKET_STRUCTURE_COPY.get(regime, "Watching: the tape has not formed a clean market read yet.")


# ---------------------------------------------------------------------------
# Optional chart attachment (matplotlib)
# ---------------------------------------------------------------------------


async def _fetch_chart_data(asset: str, venue: str, n_minutes: int = 60) -> list[dict]:
    """Fetch recent chart bars for the chart attachment. Returns [] on error."""
    url = f"{API_BASE}/api/chart/{asset}/{venue}?n_minutes={n_minutes}"
    try:
        async with aiohttp.ClientSession() as s:
            async with s.get(url, timeout=aiohttp.ClientTimeout(total=5)) as r:
                if r.status != 200:
                    return []
                data = await r.json()
                return data.get("data") or []
    except Exception:
        return []


def _render_chart_png(asset: str, venue: str, bars: list[dict]) -> bytes | None:
    """Render a small price + buy/sell volume chart as a PNG byte buffer.
    Returns None if matplotlib isn't installed or rendering fails."""
    if not bars:
        return None
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        import numpy as np
    except Exception:
        return None
    try:
        prices = np.array([b.get("price", 0) for b in bars], dtype=float)
        buys = np.array([b.get("buy_volume", 0) for b in bars], dtype=float)
        sells = np.array([b.get("sell_volume", 0) for b in bars], dtype=float)
        x = np.arange(len(bars))

        fig, (ax_p, ax_v) = plt.subplots(
            2, 1, figsize=(8, 4), gridspec_kw={"height_ratios": [3, 1]},
            sharex=True,
        )
        fig.patch.set_facecolor("#0f172a")
        for ax in (ax_p, ax_v):
            ax.set_facecolor("#0f172a")
            for sp in ax.spines.values():
                sp.set_color("#475569")
            ax.tick_params(colors="#94a3b8", labelsize=8)

        upish = prices[-1] >= prices[0]
        ax_p.plot(x, prices, color=("#34d399" if upish else "#fb7185"), linewidth=1.6)
        ax_p.set_title(f"{asset}-USD on {venue} · last {len(bars)} min",
                        color="#cbd5e1", fontsize=10, loc="left")
        ax_p.set_ylabel("price", color="#94a3b8", fontsize=8)
        ax_p.grid(True, color="#1e293b", linewidth=0.5)

        ax_v.bar(x, buys,   color="#10b981", alpha=0.8, width=0.9, label="buy")
        ax_v.bar(x, -sells, color="#f43f5e", alpha=0.8, width=0.9, label="sell")
        ax_v.axhline(0, color="#475569", linewidth=0.6)
        ax_v.set_ylabel("buy / sell", color="#94a3b8", fontsize=8)
        ax_v.set_xlabel("minutes ago", color="#94a3b8", fontsize=8)
        ax_v.grid(True, color="#1e293b", linewidth=0.5, axis="y")

        fig.tight_layout()
        buf = io.BytesIO()
        fig.savefig(buf, format="png", dpi=110, facecolor=fig.get_facecolor())
        plt.close(fig)
        buf.seek(0)
        return buf.getvalue()
    except Exception as e:
        print(f"[discord-bot] chart render failed: {e}", flush=True)
        return None


# ---------------------------------------------------------------------------
# Embed building
# ---------------------------------------------------------------------------


def _set_branding(e: discord.Embed):
    if BOT_AVATAR_URL:
        e.set_author(name=BOT_DISPLAY_NAME, icon_url=BOT_AVATAR_URL)
    else:
        e.set_author(name=BOT_DISPLAY_NAME)


def make_main_embed(sig: dict) -> discord.Embed:
    base_color, label, emoji = REGIME_STYLES.get(sig["regime"], REGIME_STYLES["UNKNOWN"])
    cascade_event = sig.get("cascade_event") or ""
    cvm = sig.get("cross_venue_multiplier", 1.0)
    conf = sig.get("adjusted_confidence", sig.get("confidence", 0.0))
    color = _confidence_color(base_color, float(conf))

    title_prefix = ""
    if cascade_event.startswith("CROSS_VENUE_WHALE_HERD"):
        title_prefix = "🌊🌊 CROSS-VENUE CASCADE — "
    elif cascade_event.startswith("WHALE_TO_HERD"):
        title_prefix = "🌊 WHALE→HERD CASCADE — "

    headline = sig.get("event_label") or label
    drift = sig.get("drift_status") or ""
    drift_marker = ""
    if drift == "unstable":
        drift_marker = " ⚠ unstable"
    elif drift == "recently_flipped":
        drift_marker = " ⚠ recently-flipped"
    elif drift == "decaying":
        drift_marker = " ⚠ edge-decaying"
    structure = _market_structure(sig.get("regime", "UNKNOWN"))
    playbook = sig.get("playbook") or ""
    desc_parts = [f"**Market structure:** {structure}"]
    if playbook:
        desc_parts.append(f"**Playbook:** {playbook}")
    signal_url = _signal_url(sig)
    if signal_url:
        desc_parts.append(f"[Open signal detail]({signal_url})")

    e = discord.Embed(
        title=f"{title_prefix}{emoji} {headline}{drift_marker} - {sig['asset']}-USD on {sig['venue']}",
        description="\n\n".join(desc_parts),
        color=color,
        timestamp=datetime.fromtimestamp(sig["timestamp_utc"], tz=timezone.utc),
    )
    _set_branding(e)

    # Price + bid/ask
    price = sig.get("current_price", 0.0)
    bid = sig.get("current_bid", 0.0)
    ask = sig.get("current_ask", 0.0)
    spread = (ask - bid) if (bid and ask) else 0.0
    e.add_field(name="Price", value=_fmt_price(price), inline=True)
    e.add_field(
        name="Bid / Ask",
        value=(f"{_fmt_price(bid)} / {_fmt_price(ask)}"
               + (f"  (spread {_fmt_price(spread)})" if spread else ""))
              if (bid or ask) else "—",
        inline=True,
    )
    cv_text = "confirmed" if cvm > 1.0 else "single venue" if cvm < 1.0 else "watching"
    e.add_field(name="Read", value=f"{_read_quality_label(sig)} ({cv_text})", inline=True)

    # Aggressor split
    buy_v = sig.get("chunk_buy_volume", 0.0)
    sell_v = sig.get("chunk_sell_volume", 0.0)
    total_v = buy_v + sell_v
    n_tr = sig.get("chunk_n_trades", 0)
    if total_v > 0:
        buy_pct = buy_v / total_v * 100
        leader = "buy" if buy_pct >= 50 else "sell"
        leader_pct = max(buy_pct, 100 - buy_pct)
        e.add_field(
            name=f"Flow: {leader_pct:.0f}% {leader}",
            value=(f"**{buy_pct:.0f}% buy / {100 - buy_pct:.0f}% sell**\n"
                   f"buy {_fmt_qty(buy_v)}  ·  sell {_fmt_qty(sell_v)}\n"
                   f"total {_fmt_qty(total_v)} {sig['asset']}"
                   + (f"  ·  {n_tr} trades" if n_tr else "")),
            inline=False,
        )
    elif n_tr:
        e.add_field(name="Trades", value=f"{n_tr}", inline=False)

    tape_url = _tape_url(sig)
    if tape_url:
        e.add_field(name="Open tape", value=f"[{sig['asset']}-USD on {sig['venue']}]({tape_url})", inline=False)

    e.set_footer(text=f"signal_id={sig.get('signal_id', '?')} · research, not advice · closed group")
    return e


def make_cascade_secondary_embed(sig: dict) -> discord.Embed | None:
    """Second embed posted alongside the main one when a cascade event
    fires. Provides extra context — for cross-venue cascade, a side-by-
    side WHALE / HERD breakdown; for WHALE→HERD, the prior-chunk note.
    Returns None if there's no cascade.
    """
    cascade_event = sig.get("cascade_event") or ""
    if not cascade_event:
        return None
    base_color = 0xf59e0b   # amber for all cascade-secondary panels
    e = discord.Embed(
        title="🌊 cascade detail",
        description=sig.get("cascade_detail") or cascade_event,
        color=base_color,
    )
    if cascade_event.startswith("CROSS_VENUE_WHALE_HERD"):
        e.add_field(
            name="Why this read is cleaner",
            value=("Two independent venues are showing complementary "
                   "signal types in the same direction over the same "
                   "wall-clock window. Whale + herd alignment across "
                   "venues is the cleanest signal we emit."),
            inline=False,
        )
    elif cascade_event.startswith("WHALE_TO_HERD"):
        e.add_field(
            name="Why this read is cleaner",
            value=("A big actor's flow tripped a multi-actor cascade in "
                   "the same direction with no quiet between them. Two "
                   "structurally distinct signals align — typical "
                   "whale-trips-the-herd pattern."),
            inline=False,
        )
    e.set_footer(text="read quality improves with cross-venue confirmation")
    return e


# ---------------------------------------------------------------------------
# Posting path
# ---------------------------------------------------------------------------


async def post_signal(channel: discord.abc.Messageable, sig: dict):
    """Post the main embed, optional secondary cascade embed, and (if
    enabled and matplotlib is available) a price/volume chart attachment.
    """
    embeds = [make_main_embed(sig)]
    sec = make_cascade_secondary_embed(sig)
    if sec is not None:
        embeds.append(sec)

    file = None
    if ATTACH_CHART:
        bars = await _fetch_chart_data(sig.get("asset", ""), sig.get("venue", ""))
        png = _render_chart_png(sig.get("asset", ""), sig.get("venue", ""), bars)
        if png:
            file = discord.File(io.BytesIO(png), filename="chart.png")
            # Inline the chart in the main embed
            embeds[0].set_image(url="attachment://chart.png")

    try:
        if file:
            await channel.send(embeds=embeds, file=file)
        else:
            await channel.send(embeds=embeds)
    except Exception as e:
        print(f"[discord-bot] post error: {e}", flush=True)


# ---------------------------------------------------------------------------
# Drift alert posting — separate from signal posts so the visual treatment
# is distinct (yellow border, no chart attachment, prominent ⚠ marker).
# ---------------------------------------------------------------------------


_DRIFT_TYPE_TITLES = {
    "direction_flip": "⚠ Direction flip",
    "edge_decay": "↓ Edge decaying",
    "edge_strengthen": "↑ Edge strengthening",
    "sample_milestone": "✓ Sample milestone",
    "outcome_contradiction_streak": "⚠ Outcome contradiction streak",
    "pressure_watch_high_priority": "⚠ Pressure forming",
}


async def post_drift_alert(channel: discord.abc.Messageable, alert: dict):
    """Post a drift alert as a yellow embed. Distinct from regular signals
    so users notice their playbook read may be shifting."""
    a_type = alert.get("type", "drift")
    title = _DRIFT_TYPE_TITLES.get(a_type, "Drift event")
    key = alert.get("key", "?")
    summary = alert.get("summary", "")
    color = 0xf59e0b   # amber for all drift events
    if a_type == "edge_strengthen":
        color = 0x10b981
    e = discord.Embed(
        title=f"{title} — {key}",
        description=summary or "(no summary)",
        color=color,
        timestamp=datetime.fromtimestamp(alert.get("ts_utc", 0), tz=timezone.utc),
    )
    _set_branding(e)
    # Surface the discriminating fields per type
    if a_type == "direction_flip":
        e.add_field(name="From → To",
                    value=f"{alert.get('from')} → {alert.get('to')}", inline=True)
        e.add_field(name="r change",
                    value=f"{alert.get('prev_r')} → {alert.get('cur_r')}", inline=True)
        e.add_field(name="n change",
                    value=f"{alert.get('prev_n')} → {alert.get('cur_n')}", inline=True)
    elif a_type in ("edge_decay", "edge_strengthen"):
        trend = alert.get("abs_r_trend") or []
        e.add_field(name="|r| trend (last 3)",
                    value="  →  ".join(f"{v}" for v in trend) or "—",
                    inline=False)
    elif a_type == "outcome_contradiction_streak":
        e.add_field(name="Streak", value=str(alert.get("streak", "?")), inline=True)
        e.add_field(name="Cell predicted",
                    value=alert.get("expected_direction", "?"), inline=True)
    elif a_type == "pressure_watch_high_priority":
        e.add_field(name="Direction", value=alert.get("direction", "?"), inline=True)
        e.add_field(name="Venues", value=", ".join(alert.get("venues") or []) or "—", inline=True)
        reasons = alert.get("reasons") or []
        if reasons:
            e.add_field(name="Why", value="\n".join(f"- {r}" for r in reasons[:4]), inline=False)
    e.set_footer(text=f"alert_id={alert.get('id', '?')} · review the registry on next rebuild")
    try:
        await channel.send(embed=e)
    except Exception as ex:
        print(f"[discord-bot] drift post error: {ex}", flush=True)


# ---------------------------------------------------------------------------
# SSE listener
# ---------------------------------------------------------------------------


async def resolve_signal_channel():
    channel = client.get_channel(CHANNEL_ID)
    if channel is not None:
        return channel

    try:
        return await client.fetch_channel(CHANNEL_ID)
    except discord.Forbidden:
        print(
            f"[discord-bot] cannot access channel id {CHANNEL_ID}; "
            "invite the bot to the server and grant View Channel + Send Messages",
            flush=True,
        )
    except discord.NotFound:
        print(
            f"[discord-bot] channel id {CHANNEL_ID} does not exist or the bot is not in that server",
            flush=True,
        )
    except Exception as ex:
        print(f"[discord-bot] channel lookup error for {CHANNEL_ID}: {ex}", flush=True)
    return None


@tasks.loop(reconnect=True)
async def stream_listener():
    channel = await resolve_signal_channel()
    if channel is None:
        await asyncio.sleep(5)
        return

    timeout = aiohttp.ClientTimeout(total=None, sock_read=60)
    async with aiohttp.ClientSession(timeout=timeout) as session:
        try:
            async with session.get(f"{API_BASE}/api/stream") as resp:
                if resp.status != 200:
                    print(f"[discord-bot] stream HTTP {resp.status}; retrying")
                    await asyncio.sleep(5)
                    return
                event_type = None
                async for raw in resp.content:
                    line = raw.decode("utf-8", errors="ignore").rstrip("\n")
                    if line.startswith("event:"):
                        event_type = line.split(":", 1)[1].strip()
                    elif line.startswith("data:"):
                        payload = line.split(":", 1)[1].strip()
                        if event_type == "signal" and payload:
                            try:
                                sig = json.loads(payload)
                                await post_signal(channel, sig)
                            except Exception as ex:
                                print(f"[discord-bot] post error: {ex}")
                        elif event_type == "drift_alert" and payload:
                            try:
                                alert = json.loads(payload)
                                await post_drift_alert(channel, alert)
                            except Exception as ex:
                                print(f"[discord-bot] drift post error: {ex}")
                        event_type = None
        except Exception as ex:
            print(f"[discord-bot] stream error: {ex}; will retry")
            await asyncio.sleep(5)


@stream_listener.before_loop
async def before():
    await client.wait_until_ready()


# ---------------------------------------------------------------------------
# Slash commands
# ---------------------------------------------------------------------------


@tree.command(name="status", description="Current Whale, Herd, and Equilibrium reads by asset and venue")
async def cmd_status(interaction: discord.Interaction):
    await interaction.response.defer(thinking=True)
    async with aiohttp.ClientSession() as s:
        async with s.get(f"{API_BASE}/api/status") as r:
            data = await r.json()
    statuses = data.get("statuses", [])
    if not statuses:
        await interaction.followup.send("No market reads yet.")
        return
    lines = []
    for st in statuses:
        emoji = REGIME_STYLES.get(st["regime"], REGIME_STYLES["UNKNOWN"])[2]
        label = REGIME_STYLES.get(st["regime"], REGIME_STYLES["UNKNOWN"])[1]
        price = _fmt_price(st.get("current_price", 0))
        cvm = st.get("cross_venue_multiplier", 1.0)
        venue_note = "confirmed" if cvm > 1.0 else "single" if cvm < 1.0 else "watch"
        pressure = "" if st.get("pressure_watch_state") == "internal" else (st.get("pressure_watch_label") or "")
        pressure_note = f"  | {pressure}" if pressure else ""
        lines.append(
            f"{emoji} `{st['asset']}-USD on {st['venue']:<8}` {label:<22}  "
            f"{price}  read {_read_quality_label(st):<12}  {venue_note}{pressure_note}"
        )
    await interaction.followup.send("```\n" + "\n".join(lines) + "\n```")


@tree.command(name="stats", description="Recent signal counts by market read and asset")
async def cmd_stats(interaction: discord.Interaction, limit: int = 50):
    await interaction.response.defer(thinking=True)
    async with aiohttp.ClientSession() as s:
        async with s.get(f"{API_BASE}/api/signals?limit={limit}") as r:
            data = await r.json()
    sigs = data.get("signals", [])
    if not sigs:
        await interaction.followup.send("No signals yet.")
        return
    from collections import Counter
    by_read = Counter(REGIME_STYLES.get(s["regime"], REGIME_STYLES["UNKNOWN"])[1] for s in sigs)
    by_asset = Counter(s["asset"] for s in sigs)
    n_cascade = sum(1 for s in sigs if s.get("cascade_event"))
    lines = [
        f"Last {len(sigs)} signals · {n_cascade} cross-venue cascade",
        "By market read:",
        *[f"  {r}: {n}" for r, n in by_read.most_common()],
        "By asset:",
        *[f"  {a}: {n}" for a, n in by_asset.most_common()],
    ]
    await interaction.followup.send("```\n" + "\n".join(lines) + "\n```")


@tree.command(name="tape", description="Open the mobile tape view for an asset and venue")
async def cmd_tape(interaction: discord.Interaction, asset: str = "BTC", venue: str = "bybit"):
    url = _app_url(f"/tape/{asset.upper()}/{venue.lower()}")
    if not url:
        await interaction.response.send_message("Set MARKETS_WATCH_APP_URL on the bot to enable app links.", ephemeral=True)
        return
    await interaction.response.send_message(f"Open tape: {url}")


def main():
    if not BOT_TOKEN:
        raise SystemExit("set DISCORD_BOT_TOKEN")
    if CHANNEL_ID == 0:
        raise SystemExit("set DISCORD_CHANNEL_ID")
    client.run(BOT_TOKEN)


if __name__ == "__main__":
    main()
