"""
api.py  –  PS99 BIG Games API + Roblox API wrapper
Pull → Save → Compare
"""

import aiohttp
import asyncio
from config import API_BASE, IMAGE_BASE, ROBLOX_USERS, ROBLOX_USER_URL

_TIMEOUT = aiohttp.ClientTimeout(total=15)

# ── low-level ──────────────────────────────────────────────────────────────────
async def _get(session: aiohttp.ClientSession, url: str):
    try:
        async with session.get(url, timeout=_TIMEOUT) as r:
            if r.status != 200:
                return None
            j = await r.json(content_type=None)
            return j.get("data") if j.get("status") == "ok" else None
    except Exception:
        return None

# ── clan ───────────────────────────────────────────────────────────────────────
async def get_clan(session: aiohttp.ClientSession, name: str) -> dict | None:
    return await _get(session, f"{API_BASE}/clan/{name}")

async def get_clans_page(session: aiohttp.ClientSession,
                         page: int = 1, page_size: int = 50) -> list | None:
    url = f"{API_BASE}/clans?page={page}&pageSize={page_size}&sort=Points&sortOrder=desc"
    return await _get(session, url)

async def get_top_clans(session: aiohttp.ClientSession, n: int = 10) -> list:
    data = await get_clans_page(session, page=1, page_size=n)
    return data or []

async def get_clan_rank(session: aiohttp.ClientSession, name: str) -> int | None:
    """
    Schnelle Rank-Suche: holt erst den Clan direkt um seine Points zu kennen,
    dann berechnet wie viele Clans mehr Punkte haben = Rang.
    Nur 2 API-Calls statt hunderte!
    """
    name_up = name.upper()

    # Schritt 1: Clan-Daten holen (kennen wir schon meistens)
    clan_data = await get_clan(session, name)
    if not clan_data:
        return None

    clan_pts = total_points(clan_data)

    # Schritt 2: Scan parallel in Batches bis wir den Clan finden
    # Maximal 20 Seiten à 50 = Top 1000
    BATCH = 5
    PAGE_SIZE = 50

    for start in range(1, 21, BATCH):
        pages = list(range(start, min(start + BATCH, 21)))
        results = await asyncio.gather(
            *[get_clans_page(session, p, PAGE_SIZE) for p in pages],
            return_exceptions=True
        )
        for p, batch in zip(pages, results):
            if not batch or isinstance(batch, Exception):
                continue
            for i, c in enumerate(batch):
                if (c.get("Name") or "").upper() == name_up:
                    return (p - 1) * PAGE_SIZE + i + 1
        # Früh aufhören wenn wir die Points des Clans überschritten haben
        for batch in results:
            if isinstance(batch, list) and batch:
                last_pts = total_points_leaderboard(batch[-1])
                if last_pts < clan_pts * 0.5:
                    # Wir sind weit genug – Clan nicht in Top 1000
                    return None

    return None

async def get_active_clan_battle(session: aiohttp.ClientSession) -> dict | None:
    return await _get(session, f"{API_BASE}/activeClanBattle")

# ── data helpers ───────────────────────────────────────────────────────────────
def total_points(clan: dict) -> int:
    battle = clan.get("Contribution", {}).get("Battle", [])
    return sum(m.get("Points", 0) for m in battle)

def total_points_leaderboard(clan: dict) -> int:
    """Points from leaderboard entry (has 'Points' directly)."""
    return clan.get("Points", 0)

def hourly_points(clan: dict) -> int:
    hourly = clan.get("Contribution", {}).get("Hourly", [])
    return sum(m.get("Points", 0) for m in hourly)

def deposited_diamonds(clan: dict) -> float:
    return clan.get("DepositedDiamonds", 0) or 0

def member_ids(clan: dict) -> list[int]:
    return [m["UserID"] for m in clan.get("Members", []) if "UserID" in m]

def battle_sorted(clan: dict) -> list[dict]:
    return sorted(
        clan.get("Contribution", {}).get("Battle", []),
        key=lambda x: x.get("Points", 0),
        reverse=True
    )

# ── Roblox ─────────────────────────────────────────────────────────────────────
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
            ROBLOX_USER_URL.format(uid=uid), timeout=_TIMEOUT
        ) as r:
            d = await r.json(content_type=None)
            return d.get("name")
    except Exception:
        return None

async def roblox_names_bulk(session: aiohttp.ClientSession,
                            uids: list[int]) -> dict[int, str]:
    result = {}
    async def _fetch(uid):
        name = await roblox_name(session, uid)
        if name:
            result[uid] = name
    for chunk in [uids[i:i+10] for i in range(0, len(uids), 10)]:
        await asyncio.gather(*[_fetch(u) for u in chunk])
    return result

def icon_url(asset_id: str | None) -> str | None:
    if not asset_id:
        return None
    raw = str(asset_id).replace("rbxassetid://", "")
    return f"{IMAGE_BASE}/{raw}"
