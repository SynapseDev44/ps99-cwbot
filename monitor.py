"""
monitor.py  –  Pull → Save → Compare
Pollt alle POLL_INTERVAL Sekunden jeden getracken Clan.
Vergleicht mit dem letzten Snapshot und feuert Events:
  • Rang geändert      → ranking_change embed
  • Member joined/left → player_joined / player_left embed
  • Diamonds erhöht    → diamond_update embed (auto-detected)
  • Jede Stunde        → hourly_update embed
"""

import asyncio
import time
import aiohttp

import api  as ps99
import db
import embeds
from config import POLL_INTERVAL
from fmt import fmt

class Monitor:
    def __init__(self, bot):
        self.bot       = bot
        self._running  = False
        self._last_hr: dict[str, float] = {}   # clan_name → last hourly ts

    def start(self):
        self._running = True
        asyncio.create_task(self._loop())
        print("✅ Monitor gestartet")

    def stop(self):
        self._running = False

    # ── main loop ──────────────────────────────────────────────────────────────
    async def _loop(self):
        await self.bot.wait_until_ready()
        async with aiohttp.ClientSession() as session:
            while self._running:
                await self._tick(session)
                await asyncio.sleep(POLL_INTERVAL)

    async def _tick(self, session: aiohttp.ClientSession):
        tracked   = db.get_all_tracked()
        # deduplicate: only poll each clan once even if tracked on multiple guilds
        seen_clans: dict[str, dict] = {}   # clan_name → fresh data
        for entry in tracked:
            cname = entry["clan_name"]
            if cname not in seen_clans:
                data = await ps99.get_clan(session, cname)
                seen_clans[cname] = data  # may be None on API error

        for entry in tracked:
            try:
                await self._process(session, entry, seen_clans[entry["clan_name"]])
            except Exception as exc:
                print(f"❌ Monitor [{entry['clan_name']}] {exc}")

    async def _process(self, session, entry: dict, data: dict | None):
        if data is None:
            return

        clan_name = entry["clan_name"]
        notifs    = entry.get("notifs", {})
        guild_id  = entry["guild_id"]
        channel   = self.bot.get_channel(int(entry["channel_id"]))

        prev      = db.latest_snapshot(clan_name)
        pts_now   = ps99.total_points(data)
        hrly_now  = ps99.hourly_points(data)
        dia_now   = ps99.deposited_diamonds(data)
        ids_now   = ps99.member_ids(data)
        capacity  = data.get("MemberCapacity", 75)

        # ── RANK ────────────────────────────────────────────────────────────
        rank_now  = await ps99.get_clan_rank(session, clan_name)
        rank_prev = db.last_rank(clan_name)

        if channel and notifs.get("ranking", True):
            if rank_now and rank_prev and rank_now != rank_prev:
                emb = embeds.ranking_change(clan_name, rank_prev, rank_now, pts_now)
                await channel.send(embed=emb)

        # ── JOIN / LEAVE ────────────────────────────────────────────────────
        if prev and channel and notifs.get("join_leave", True):
            prev_ids = set(prev.get("members", []))
            curr_ids = set(ids_now)

            for uid in curr_ids - prev_ids:
                name = await self._resolve_name(session, uid)
                emb  = embeds.player_joined(name, len(curr_ids), capacity, clan_name)
                await channel.send(embed=emb)

            for uid in prev_ids - curr_ids:
                name = await self._resolve_name(session, uid)
                emb  = embeds.player_left(name, len(curr_ids), capacity, clan_name)
                await channel.send(embed=emb)

        # ── DIAMONDS (auto-detect donation) ────────────────────────────────
        if prev and channel and notifs.get("diamond", True):
            prev_dia = prev.get("diamonds", 0)
            if dia_now > prev_dia:
                delta = dia_now - prev_dia
                emb   = embeds.diamond_update(
                    clan_name, "Unbekannt", delta, delta, dia_now
                )
                await channel.send(embed=emb)

        # ── HOURLY UPDATE ───────────────────────────────────────────────────
        now = time.time()
        if now - self._last_hr.get(clan_name, 0) >= 3600:
            self._last_hr[clan_name] = now
            if channel and notifs.get("hourly", True):
                diff = db.hourly_diff(clan_name)
                emb  = embeds.hourly_update(data, clan_name, rank_now, hrly_now, diff)
                await channel.send(embed=emb)

        # ── SAVE SNAPSHOT ───────────────────────────────────────────────────
        db.push_snapshot(clan_name, pts_now, rank_now, ids_now, dia_now)
        if rank_now:
            db.save_rank(clan_name, rank_now)

    # ── Roblox name helper (with cache) ────────────────────────────────────────
    async def _resolve_name(self, session, uid: int) -> str:
        cached = db.cached_name(uid)
        if cached:
            return cached
        name = await ps99.roblox_name(session, uid) or str(uid)
        db.cache_name(uid, name)
        return name
