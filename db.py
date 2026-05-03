"""
db.py  –  JSON-Datenbank mit GitHub-Gist-Backup
Per-Notification-Type Channel Struktur
"""

import json, time, copy
from pathlib import Path
import aiohttp
from config import MAX_SNAPSHOTS, GIST_ID, GITHUB_TOKEN

DB_PATH = Path("data/db.json")

_EMPTY = {
    "guilds":        {},
    "snapshots":     {},
    "ranks":         {},
    "league_ranks":  {},
    "uid_cache":     {},
}

_db: dict = {}

# ── Migration: altes Format → neues Format ─────────────────────────
_ALL_TYPES = ("clanrank", "diamonds", "hourlystats", "joinleave", "leagues")

def _migrate_clan(cdata: dict) -> dict:
    if "channels" not in cdata:
        old_ch = cdata.get("channel_id", "")
        old_n  = cdata.get("notifs", {})
        cdata = {
            "channels": {
                "clanrank":    old_ch if old_n.get("ranking",    True) else "",
                "diamonds":    old_ch if old_n.get("diamond",    True) else "",
                "hourlystats": old_ch if old_n.get("hourly",     True) else "",
                "joinleave":   old_ch if old_n.get("join_leave", True) else "",
                "leagues":     "",
            },
            "disabled": {
                "clanrank":    not old_n.get("ranking",    True),
                "diamonds":    not old_n.get("diamond",    True),
                "hourlystats": not old_n.get("hourly",     True),
                "joinleave":   not old_n.get("join_leave", True),
                "leagues":     False,
            },
        }
    else:
        # Ensure new keys exist in old new-format entries
        cdata.setdefault("channels", {}).setdefault("leagues", "")
        cdata.setdefault("disabled", {}).setdefault("leagues", False)
    return cdata

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
    _db = copy.deepcopy(_EMPTY)
    for k in _EMPTY:
        if k in loaded:
            _db[k] = loaded[k]
    for gid, gdata in _db.get("guilds", {}).items():
        for cname in list(gdata.get("clans", {}).keys()):
            gdata["clans"][cname] = _migrate_clan(gdata["clans"][cname])
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
    if key not in _db:
        _db[key] = copy.deepcopy(_EMPTY[key])
    return _db[key]

# ── guild / clan helpers ───────────────────────────────────────────
def _guild(guild_id: str) -> dict:
    guilds = _g("guilds")
    if guild_id not in guilds:
        guilds[guild_id] = {"clans": {}}
    guilds[guild_id].setdefault("clans", {})
    return guilds[guild_id]

def _clan(guild_id: str, clan_name: str) -> dict:
    clan_up = clan_name.upper()
    clans = _guild(guild_id)["clans"]
    if clan_up not in clans:
        clans[clan_up] = {
            "channels": {t: "" for t in _ALL_TYPES},
            "disabled": {t: False for t in _ALL_TYPES},
        }
    return clans[clan_up]

# ── tracking ───────────────────────────────────────────────────────
def set_clan_channel(guild_id: str, clan_name: str, notif_type: str, channel_id: str):
    entry = _clan(guild_id, clan_name)
    entry.setdefault("channels", {})[notif_type] = channel_id
    entry.setdefault("disabled", {})[notif_type] = False
    save()

def disable_notif(guild_id: str, clan_name: str, notif_type: str) -> bool:
    clan_up = clan_name.upper()
    clans = _guild(guild_id).get("clans", {})
    if clan_up not in clans:
        return False
    clans[clan_up].setdefault("disabled", {})[notif_type] = True
    save()
    return True

def get_notif_channel(guild_id: str, clan_name: str, notif_type: str) -> str | None:
    clan_up = clan_name.upper()
    clans = _guild(guild_id).get("clans", {})
    if clan_up not in clans:
        return None
    entry = clans[clan_up]
    if entry.get("disabled", {}).get(notif_type, False):
        return None
    ch = entry.get("channels", {}).get(notif_type, "")
    return ch if ch else None

def get_clan_entry(guild_id: str, clan_name: str) -> dict | None:
    return _guild(guild_id)["clans"].get(clan_name.upper())

def get_server_clans(guild_id: str) -> dict:
    return _guild(guild_id).get("clans", {})

def remove_clan(guild_id: str, clan_name: str) -> bool:
    clans = _guild(guild_id).get("clans", {})
    clan_up = clan_name.upper()
    if clan_up in clans:
        del clans[clan_up]
        save()
        return True
    return False

def get_all_tracked() -> list[dict]:
    result = []
    for gid, gdata in _g("guilds").items():
        for cname, cdata in gdata.get("clans", {}).items():
            channels = cdata.get("channels", {})
            if any(v for v in channels.values()):
                result.append({
                    "guild_id":  gid,
                    "clan_name": cname,
                    "channels":  channels,
                    "disabled":  cdata.get("disabled", {}),
                })
    return result

# ── snapshots ──────────────────────────────────────────────────────
def push_snapshot(clan_name: str, points: int, rank, members: list,
                  diamonds: float, member_diamonds: dict = None,
                  member_battle: dict = None):
    key = clan_name.upper()
    snaps = _g("snapshots").setdefault(key, [])
    snaps.insert(0, {
        "ts":              int(time.time()),
        "points":          points,
        "rank":            rank,
        "members":         members,
        "diamonds":        diamonds,
        "member_diamonds": {str(k): v for k, v in (member_diamonds or {}).items()},
        "member_battle":   {str(k): v for k, v in (member_battle  or {}).items()},
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

# ── CW ranks ───────────────────────────────────────────────────────
def save_rank(clan_name: str, rank: int):
    _g("ranks")[clan_name.upper()] = rank
    save()

def last_rank(clan_name: str) -> int | None:
    return _g("ranks").get(clan_name.upper())

# ── League ranks ────────────────────────────────────────────────────
def save_league_rank(clan_name: str, rank: int):
    _g("league_ranks")[clan_name.upper()] = rank
    save()

def last_league_rank(clan_name: str) -> int | None:
    return _g("league_ranks").get(clan_name.upper())

# ── name cache ─────────────────────────────────────────────────────
def cache_name(uid: int, name: str):
    _g("uid_cache")[str(uid)] = name
    save()

def cached_name(uid) -> str | None:
    return _g("uid_cache").get(str(uid))

# ── init ───────────────────────────────────────────────────────────
_load()
