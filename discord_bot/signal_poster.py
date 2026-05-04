"""
signal_poster.py — Discord bot for the markets-watch closed signal feed.

Subscribes to the backend's SSE stream at /api/stream and posts each signal
event to a configured Discord channel as a rich embed. Color-codes by regime.
Provides slash commands for self-service stats.

Setup:
  1. Create a Discord application at https://discord.com/developers/applications
  2. Add a bot, copy the bot token, set DISCORD_BOT_TOKEN env var
  3. Invite bot to your server with permissions: Send Messages, Embed Links,
     Read Message History, Use Slash Commands
  4. Set DISCORD_CHANNEL_ID env var to the channel where signals should post
  5. Set MARKETS_WATCH_API env var to your backend URL (default localhost:8000)

Run: python signal_poster.py
"""

from __future__ import annotations

import asyncio
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


# Regime → (color int, label, emoji)
REGIME_STYLES = {
    "WHALE_UP":             (0x22c55e, "WHALE ↑",       "🟢"),
    "WHALE_DOWN":           (0xef4444, "WHALE ↓",       "🔴"),
    "HERD_UP":              (0xf97316, "HERD ↑ (FOMO)", "🟠"),
    "HERD_DOWN":            (0xb91c1c, "HERD ↓ (panic)", "🟤"),
    "EQUILIBRIUM_TWO_SIDED":(0x3b82f6, "EQUILIBRIUM",   "🔵"),
    "WASH_PAIRED":          (0xeab308, "WASH ⚠",        "🟡"),
    "DEPLETED":             (0x9ca3af, "DEPLETED",      "⚪"),
    "UNKNOWN":              (0x6b7280, "UNKNOWN",       "❓"),
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


def make_embed(sig: dict) -> discord.Embed:
    color, label, emoji = REGIME_STYLES.get(sig["regime"], REGIME_STYLES["UNKNOWN"])
    e = discord.Embed(
        title=f"{emoji} {label} — {sig['asset']}-USD on {sig['venue']}",
        description=sig.get("playbook", "(no playbook)"),
        color=color,
        timestamp=datetime.fromtimestamp(sig["timestamp_utc"], tz=timezone.utc),
    )
    e.add_field(name="Dipole",        value=f"{sig['mean_dipole']:+.3f}", inline=True)
    e.add_field(name="Realized vol",  value=f"{sig['realized_vol'] * 1e4:.1f} bp", inline=True)
    cvm = sig.get("cross_venue_multiplier", 1.0)
    cv_text = "✓ confirmed" if cvm > 1.0 else "✗ single-venue" if cvm < 1.0 else "—"
    conf = sig.get("adjusted_confidence", sig.get("confidence", 0.0))
    e.add_field(name="Confidence", value=f"{conf * 100:.0f}% ({cv_text})", inline=True)
    if sig.get("notes"):
        e.add_field(name="Why", value="\n".join(f"• {n}" for n in sig["notes"][:2]), inline=False)
    e.set_footer(text=f"signal_id={sig.get('signal_id', '?')} · research, not advice")
    return e


@tasks.loop(reconnect=True)
async def stream_listener():
    """Long-lived loop: connect to backend SSE, post each signal to Discord."""
    channel = client.get_channel(CHANNEL_ID)
    if channel is None:
        print(f"[discord-bot] channel id {CHANNEL_ID} not found yet")
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
                                await channel.send(embed=make_embed(sig))
                            except Exception as ex:
                                print(f"[discord-bot] post error: {ex}")
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

@tree.command(name="status", description="Current regime per asset/venue")
async def cmd_status(interaction: discord.Interaction):
    await interaction.response.defer(thinking=True)
    async with aiohttp.ClientSession() as s:
        async with s.get(f"{API_BASE}/api/status") as r:
            data = await r.json()
    statuses = data.get("statuses", [])
    if not statuses:
        await interaction.followup.send("No regime data yet.")
        return
    lines = []
    for st in statuses:
        emoji = REGIME_STYLES.get(st["regime"], REGIME_STYLES["UNKNOWN"])[2]
        lines.append(
            f"{emoji} `{st['asset']}-USD on {st['venue']:<8}` {st['regime']:<22} "
            f"dipole={st['mean_dipole']:+.3f}  conf={st.get('adjusted_confidence', st.get('confidence', 0))*100:.0f}%"
        )
    await interaction.followup.send("```\n" + "\n".join(lines) + "\n```")


@tree.command(name="stats", description="Recent signal counts and top regimes")
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
    by_regime = Counter(s["regime"] for s in sigs)
    by_asset = Counter(s["asset"] for s in sigs)
    lines = [
        f"Last {len(sigs)} signals:",
        "By regime:",
        *[f"  {r}: {n}" for r, n in by_regime.most_common()],
        "By asset:",
        *[f"  {a}: {n}" for a, n in by_asset.most_common()],
    ]
    await interaction.followup.send("```\n" + "\n".join(lines) + "\n```")


def main():
    if not BOT_TOKEN:
        raise SystemExit("set DISCORD_BOT_TOKEN")
    if CHANNEL_ID == 0:
        raise SystemExit("set DISCORD_CHANNEL_ID")
    client.run(BOT_TOKEN)


if __name__ == "__main__":
    main()
