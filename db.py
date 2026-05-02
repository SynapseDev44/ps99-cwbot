"""
db.py  –  JSON-basierte Datenbank mit optionalem GitHub-Gist-Backup
Struktur:
  guilds    → {guild_id: {clans: {clan_name: {channel_id, notifs}}}}
  snapshots → {CLAN: [{ts, points, rank, members:[uid], diamonds}]}
  donations → {CLAN: [{roblox_user, amount, discord_uid, ts}]}
  ranks     → {CLAN: int}
  uid_cache → {uid_str: username}   (Roblox name cache)
"""

import json
import time
import asyncio
from pathlib import Path
import aiohttp

from config import MAX_SNAPSHOTS, GIST_ID, GITHUB_TOKEN

DB_PATH = Path("data/db.json")

_DEFAULT: dict = {
    "guilds":    {},
    "snapshots": {},
    "donations": {},
    "ranks":     {},
    "uid_cache": {},
}

_db: dict = {}

# ── load / save ────────────────────────────────────────────────────────────────

def _load():
    global _db
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    if DB_PATH.exists():
        try:
            _db = json.loads(DB_PATH.read_text("utf-8"))
            # ensure all top-level keys exist
            for k, v in _DEFAULT.items():
                _db.setdefault(k, type(v)())
            print("✅ DB geladen")
            return
        except Exception as e:
            print(f"⚠️  DB load error: {e}")
    import copy
    _db = copy.deepcopy(_DEFAULT)
    _save_sync()
    print("✅ Neue DB erstellt")

def _save_sync():
    try:
        DB_PATH.write_text(json.dumps(_db, indent=2, ensure_ascii=False), "utf-8")
    except Exception as e:
        print(f"❌ DB save error: {e}")

def save():
    _save_sync()

# ── Gist backup ────────────────────────────────────────────────────────────────

async def gist_backup():
    if not GIST_ID or not GITHUB_TOKEN:
        return
    try:
        async with aiohttp.ClientSession() as s:
            await s.patch(
                f"https://api.github.com/gists/{GIST_ID}",
                headers={"Authorization": f"token {GITHUB_TOKEN}"},
                json={"files": {"ps99cwbot_db.json": {
                    "content": json.dumps(_db, indent=2, ensure_ascii=False)
                }}},
            )
    except Exception:
        pass

async def gist_restore():
    if not GIST_ID or not GITHUB_TOKEN:
        return
    try:
        async with aiohttp.ClientSession() as s:
            async with s.get(
                f"https://api.github.com/gists/{GIST_ID}",
                headers={"Authorization": f"token {GITHUB_TOKEN}"},
            ) as r:
                data = await r.json(content_type=None)
                content = (data.get("files") or {}).get("ps99cwbot_db.json", {}).get("content")
                if content:
                    global _db
                    _db = json.loads(content)
                    _save_sync()
                    print("✅ DB von Gist geladen")
    except Exception as e:
        print(f"⚠️  Gist restore: {e}")

# ── guild / tracking ───────────────────────────────────────────────────────────

def _guild(guild_id: str) -> dict:
    return _db["guilds"].setdefault(guild_id, {"clans": {}})

def track_clan(guild_id: str, clan_name: str, channel_id: str):
    clan_up = clan_name.upper()
    _guild(guild_id)["clans"][clan_up] = {
        "channel_id": channel_id,
        "notifs": {
            "diamond":    True,
            "join_leave": True,
            "ranking":    True,
            "hourly":     True,
        },
    }
    save()

def untrack_clan(guild_id: str, clan_name: str) -> bool:
    clans = _guild(guild_id).get("clans", {})
    clan_up = clan_name.upper()
    if clan_up in clans:
        del clans[clan_up]
        save()
        return True
    return False

def get_clan_entry(guild_id: str, clan_name: str) -> dict | None:
    return _guild(guild_id)["clans"].get(clan_name.upper())

def get_server_clans(guild_id: str) -> dict:
    """Returns {CLAN_NAME: entry} for one guild."""
    return _guild(guild_id).get("clans", {})

def get_all_tracked() -> list[dict]:
    """All tracked entries across all guilds.
    Returns list of {guild_id, clan_name, channel_id, notifs}."""
    result = []
    for gid, gdata in _db["guilds"].items():
        for cname, cdata in gdata.get("clans", {}).items():
            result.append({
                "guild_id":   gid,
                "clan_name":  cname,
                "channel_id": cdata["channel_id"],
                "notifs":     cdata.get("notifs", {}),
            })
    return result

def set_notif(guild_id: str, clan_name: str, key: str, value: bool) -> bool:
    entry = get_clan_entry(guild_id, clan_name)
    if entry is None:
        return False
    entry.setdefault("notifs", {})[key] = value
    save()
    return True

def get_notif(guild_id: str, clan_name: str, key: str) -> bool:
    entry = get_clan_entry(guild_id, clan_name)
    if entry is None:
        return False
    return entry.get("notifs", {}).get(key, True)

# ── snapshots (Pull → Save → Compare) ────────────────────────────────────────

def push_snapshot(clan_name: str, points: int, rank, members: list[int], diamonds: float):
    """Push a new snapshot. Oldest are discarded after MAX_SNAPSHOTS."""
    key = clan_name.upper()
    snaps = _db["snapshots"].setdefault(key, [])
    snaps.insert(0, {
        "ts":       int(time.time()),
        "points":   points,
        "rank":     rank,
        "members":  members,
        "diamonds": diamonds,
    })
    _db["snapshots"][key] = snaps[:MAX_SNAPSHOTS]
    save()

def latest_snapshot(clan_name: str) -> dict | None:
    snaps = _db["snapshots"].get(clan_name.upper(), [])
    return snaps[0] if snaps else None

def get_snapshots(clan_name: str, n: int = 24) -> list:
    return _db["snapshots"].get(clan_name.upper(), [])[:n]

def hourly_diff(clan_name: str) -> int | None:
    snaps = _db["snapshots"].get(clan_name.upper(), [])
    if len(snaps) < 2:
        return None
    return snaps[0]["points"] - snaps[1]["points"]

# ── rank cache ─────────────────────────────────────────────────────────────────

def save_rank(clan_name: str, rank: int):
    _db["ranks"][clan_name.upper()] = rank
    save()

def last_rank(clan_name: str) -> int | None:
    return _db["ranks"].get(clan_name.upper())

# ── diamond donations ──────────────────────────────────────────────────────────

def add_donation(clan: str, roblox_user: str, amount: float, discord_uid: str):
    clan_up = clan.upper()
    clan_donations = _db["donations"].setdefault(clan_up, [])
    existing = next(
        (d for d in clan_donations if d["roblox_user"].lower() == roblox_user.lower()),
        None
    )
    if existing:
        existing["amount"] += amount
        existing["last_ts"] = int(time.time())
    else:
        clan_donations.append({
            "roblox_user": roblox_user,
            "amount":      amount,
            "discord_uid": discord_uid,
            "ts":          int(time.time()),
            "last_ts":     int(time.time()),
        })
    save()

def get_donations(clan: str) -> list:
    return _db["donations"].get(clan.upper(), [])

def clan_diamond_total(clan: str) -> float:
    return sum(d["amount"] for d in get_donations(clan))

# ── Roblox name cache ──────────────────────────────────────────────────────────

def cache_name(uid: int, name: str):
    _db["uid_cache"][str(uid)] = name
    save()

def cached_name(uid: int) -> str | None:
    return _db["uid_cache"].get(str(uid))

# ── init ───────────────────────────────────────────────────────────────────────
_load()
