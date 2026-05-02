"""
api.py  –  PS99 BIG Games API + Roblox API wrapper
Pull → Save → Compare  (wie vom CW-Ranking Bot Owner beschrieben)
"""

import aiohttp
import asyncio
from config import API_BASE, IMAGE_BASE, ROBLOX_USERS, ROBLOX_USER_URL, RANK_SEARCH_PAGES

_TIMEOUT = aiohttp.ClientTimeout(total=12)

# ── low-level helpers ──────────────────────────────────────────────────────────

async def _get(session: aiohttp.ClientSession, url: str) -> dict | None:
    try:
        async with session.get(url, timeout=_TIMEOUT) as r:
            if r.status != 200:
                return None
            j = await r.json(content_type=None)
            if j.get("status") == "ok":
                return j.get("data")
            return None
    except Exception:
        return None

# ── clan endpoints ─────────────────────────────────────────────────────────────

async def get_clan(session: aiohttp.ClientSession, name: str) -> dict | None:
    """GET /api/clan/{name}  –  full clan object"""
    return await _get(session, f"{API_BASE}/clan/{name}")

async def get_clans_page(session: aiohttp.ClientSession,
                         page: int = 1, page_size: int = 20) -> list | None:
    """GET /api/clans  –  sorted by Points desc"""
    url = f"{API_BASE}/clans?page={page}&pageSize={page_size}&sort=Points&sortOrder=desc"
    return await _get(session, url)

async def get_top_clans(session: aiohttp.ClientSession, n: int = 10) -> list:
    """Return top-n clans from leaderboard."""
    result = []
    page = 1
    while len(result) < n:
        batch = await get_clans_page(session, page=page, page_size=min(20, n - len(result)))
        if not batch:
            break
        result.extend(batch)
        if len(batch) < 20:
            break
        page += 1
    return result[:n]

async def get_clan_rank(session: aiohttp.ClientSession, name: str) -> int | None:
    """Scan leaderboard pages to find rank of a clan."""
    name_up = name.upper()
    for page in range(1, RANK_SEARCH_PAGES + 1):
        batch = await get_clans_page(session, page=page, page_size=20)
        if not batch:
            break
        for i, c in enumerate(batch):
            if (c.get("Name") or "").upper() == name_up:
                return (page - 1) * 20 + i + 1
        if len(batch) < 20:
            break
    return None

async def get_active_clan_battle(session: aiohttp.ClientSession) -> dict | None:
    """GET /api/activeClanBattle"""
    return await _get(session, f"{API_BASE}/activeClanBattle")

# ── clan data helpers ──────────────────────────────────────────────────────────

def total_points(clan: dict) -> int:
    battle = clan.get("Contribution", {}).get("Battle", [])
    return sum(m.get("Points", 0) for m in battle)

def hourly_points(clan: dict) -> int:
    """Sum of Hourly contribution if present, else 0."""
    hourly = clan.get("Contribution", {}).get("Hourly", [])
    return sum(m.get("Points", 0) for m in hourly)

def deposited_diamonds(clan: dict) -> float:
    """DepositedDiamonds from clan data."""
    return clan.get("DepositedDiamonds", 0) or 0

def member_ids(clan: dict) -> list[int]:
    return [m["UserID"] for m in clan.get("Members", []) if "UserID" in m]

def battle_sorted(clan: dict) -> list[dict]:
    """All battle contributions sorted by Points desc."""
    return sorted(
        clan.get("Contribution", {}).get("Battle", []),
        key=lambda x: x.get("Points", 0),
        reverse=True
    )

# ── Roblox API ─────────────────────────────────────────────────────────────────

async def roblox_uid(session: aiohttp.ClientSession, username: str) -> int | None:
    try:
        async with session.post(
            ROBLOX_USERS,
            json={"usernames": [username], "excludeBannedUsers": False},
            timeout=_TIMEOUT
        ) as r:
            d = await r.json(content_type=None)
            items = d.get("data", [])
            return items[0]["id"] if items else None
    except Exception:
        return None

async def roblox_name(session: aiohttp.ClientSession, uid: int) -> str | None:
    try:
        async with session.get(
            ROBLOX_USER_URL.format(uid=uid),
            timeout=_TIMEOUT
        ) as r:
            d = await r.json(content_type=None)
            return d.get("name")
    except Exception:
        return None

async def roblox_names_bulk(session: aiohttp.ClientSession,
                            uids: list[int]) -> dict[int, str]:
    """Bulk fetch names: uid → name."""
    result = {}
    # Roblox has no bulk GET by id, fetch concurrently (max 20 at a time)
    async def _fetch(uid):
        name = await roblox_name(session, uid)
        if name:
            result[uid] = name
    for chunk in [uids[i:i+20] for i in range(0, len(uids), 20)]:
        await asyncio.gather(*[_fetch(uid) for uid in chunk])
    return result

# ── image URL helper ───────────────────────────────────────────────────────────

def icon_url(asset_id: str | None) -> str | None:
    if not asset_id:
        return None
    raw = str(asset_id).replace("rbxassetid://", "")
    return f"{IMAGE_BASE}/{raw}"
