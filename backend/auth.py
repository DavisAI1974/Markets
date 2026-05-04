"""
auth.py — minimal shared-secret auth for the closed-group API.

For Tier 1 the group is small enough that "share-the-link, share-the-token"
is the right model. No DB, no OAuth dance, no per-user state.

Set MARKETS_WATCH_ACCESS_TOKEN in the environment to enable. If unset,
the API is open (useful for local dev). Production should always set it.

Token is checked via constant-time compare to avoid timing attacks.

Discord OAuth scaffold included (commented) for future Tier 1 evolution
when the group grows beyond what a shared link can manage.
"""

from __future__ import annotations

import os
import secrets

from fastapi import Header, HTTPException, Query


ACCESS_TOKEN = os.environ.get("MARKETS_WATCH_ACCESS_TOKEN", "")


def verify_token(
    authorization: str | None = Header(default=None),
    token: str | None = Query(default=None),
):
    """FastAPI dependency. Allows token via either:
      - Authorization: Bearer <token>  (preferred for API clients)
      - ?token=<token> query string    (allowed because EventSource can't set headers)
    """
    if not ACCESS_TOKEN:
        return   # auth disabled (dev mode)

    presented: str | None = None
    if authorization and authorization.lower().startswith("bearer "):
        presented = authorization[7:].strip()
    elif token:
        presented = token.strip()

    if not presented:
        raise HTTPException(401, "missing access token (Authorization: Bearer ... or ?token=)")
    if not secrets.compare_digest(presented, ACCESS_TOKEN):
        raise HTTPException(401, "invalid access token")


# ---------------------------------------------------------------------------
# Discord OAuth scaffold (NOT WIRED YET; left here for future Tier 1 evolution)
# ---------------------------------------------------------------------------
#
# from urllib.parse import urlencode
#
# DISCORD_CLIENT_ID = os.environ.get("DISCORD_CLIENT_ID", "")
# DISCORD_CLIENT_SECRET = os.environ.get("DISCORD_CLIENT_SECRET", "")
# DISCORD_REDIRECT_URI = os.environ.get("DISCORD_REDIRECT_URI", "http://localhost:8000/api/auth/discord/callback")
# DISCORD_GUILD_ID = os.environ.get("DISCORD_GUILD_ID", "")  # closed-group server
#
# def discord_login_url() -> str:
#     return "https://discord.com/oauth2/authorize?" + urlencode({
#         "client_id": DISCORD_CLIENT_ID,
#         "redirect_uri": DISCORD_REDIRECT_URI,
#         "response_type": "code",
#         "scope": "identify guilds.members.read",
#     })
#
# # Callback exchanges code -> token, queries member's role in DISCORD_GUILD_ID,
# # issues a session cookie if member is in the closed-group server. Token-based
# # API auth (above) remains as a fallback for executor / Discord bot clients.
