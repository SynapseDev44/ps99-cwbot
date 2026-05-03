"""
db.py  –  JSON-Datenbank mit GitHub-Gist-Backup
"""

import json, time, copy
from pathlib import Path
import aiohttp
from config import MAX_SNAPSHOTS, GIST_ID, GITHUB_TOKEN

DB_PATH = Path("data/db.json")

_EMPTY = {
    "guilds":    {},
    "snapshots": {},
    "donations": {},
    "ranks":     {},
    "uid_cache": {},
}

_db: dict = {}

# ── load / save ────────────────────────────────────────────────────

def _load():
    global _db
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    loaded = {}
    if DB_PATH.exists():
        try:
            loaded = json.loads(DB_PATH.read_text("utf-8"))
        except Exception as e:
            print(f"⚠️  DB load error: {e}")
    # Merge: stelle sicher dass ALLE keys vorhanden sind
    _db = copy.deepcopy(_EMPTY)
    for k in _EMPTY:
        if k in loaded:
            _db[k] = loaded[k]
    _save_sync()
    print("✅ DB geladen")

def _save_sync():
    try:
        DB_PATH.parent.mkdir(parents=True, exist_ok=True)
        DB_PATH.write_text(json.dumps(_db, indent=2, ensure_ascii=False), "utf-8")
    except Exception as e:
        print(f"❌ DB save error: {e}")

def save():
    _save_sync()

# ── Gist ───────────────────────────────────────────────────────────

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
                    loaded = json.loads(content)
                    _db = copy.deepcopy(_EMPTY)
                    for k in _EMPTY:
                        if k in loaded:
                            _db[k] = loaded[k]
                    _save_sync()
                    print("✅ DB von Gist geladen")
    except Exception as e:
        print(f"⚠️  Gist restore: {e}")

# ── safe getter ────────────────────────────────────────────────────

def _g(key: str) -> dict:
    """Sicherer Zugriff – stellt sicher dass der key immer existiert."""
    if key not in _db:
        _db[key] = copy.deepcopy(_EMPTY[key])
    return _db[key]

# ── guild / tracking ───────────────────────────────────────────────

def _guild(guild_id: str) -> dict:
    guilds = _g("guilds")
    if guild_id not in guilds:
        guilds[guild_id] = {"clans": {}}
    if "clans" not in guilds[guild_id]:
        guilds[guild_id]["clans"] = {}
    return guilds[guild_id]

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
    return _guild(guild_id).get("clans", {})

def get_all_tracked() -> list[dict]:
    result = []
    for gid, gdata in _g("guilds").items():
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

# ── snapshots ──────────────────────────────────────────────────────

def push_snapshot(clan_name: str, points: int, rank, members: list, diamonds: float,
                  member_diamonds: dict = None):
    key = clan_name.upper()
    snaps = _g("snapshots").setdefault(key, [])
    snaps.insert(0, {
        "ts":              int(time.time()),
        "points":          points,
        "rank":            rank,
        "members":         members,
        "diamonds":        diamonds,
        "member_diamonds": {str(k): v for k, v in (member_diamonds or {}).items()},
    })
    _g("snapshots")[key] = snaps[:MAX_SNAPSHOTS]
    save()

def latest_snapshot(clan_name: str) -> dict | None:
    snaps = _g("snapshots").get(clan_name.upper(), [])
    return snaps[0] if snaps else None

def get_snapshots(clan_name: str, n: int = 24) -> list:
    return _g("snapshots").get(clan_name.upper(), [])[:n]

def hourly_diff(clan_name: str) -> int | None:
    snaps = _g("snapshots").get(clan_name.upper(), [])
    if len(snaps) < 2:
        return None
    return snaps[0]["points"] - snaps[1]["points"]

# ── ranks ──────────────────────────────────────────────────────────

def save_rank(clan_name: str, rank: int):
    _g("ranks")[clan_name.upper()] = rank
    save()

def last_rank(clan_name: str) -> int | None:
    return _g("ranks").get(clan_name.upper())

# ── donations ──────────────────────────────────────────────────────

def add_donation(clan: str, roblox_user: str, amount: float, discord_uid: str):
    clan_up = clan.upper()
    clan_donations = _g("donations").setdefault(clan_up, [])
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
    return _g("donations").get(clan.upper(), [])

def clan_diamond_total(clan: str) -> float:
    return sum(d["amount"] for d in get_donations(clan))

# ── name cache ─────────────────────────────────────────────────────

def cache_name(uid: int, name: str):
    _g("uid_cache")[str(uid)] = name
    save()

def cached_name(uid) -> str | None:
    return _g("uid_cache").get(str(uid))

# ── init ───────────────────────────────────────────────────────────
_load()