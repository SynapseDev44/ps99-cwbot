"""monitor.py – Pull → Save → Compare, sendet Bilder"""
import asyncio, time
import aiohttp
import api as ps99
import db
from image_gen import (generate_diamond_update, generate_ranking_change,
                        generate_player_event, generate_clan_board)
import discord
from config import POLL_INTERVAL


async def _bulk_names(s, clan_data: dict) -> dict:
    """Fetch Roblox usernames for all battle members, using db cache."""
    uids = [m.get("UserID") for m in clan_data.get("Contribution", {}).get("Battle", [])
            if m.get("UserID") is not None]
    uid_map: dict[int, str] = {}
    missing = []
    for uid in uids:
        cached = db.cached_name(uid)
        if cached:
            uid_map[int(uid)] = cached
        else:
            missing.append(uid)
    if missing:
        fetched = await ps99.roblox_names_bulk(s, missing)
        for uid, name in fetched.items():
            db.cache_name(uid, name)
            uid_map[int(uid)] = name
    return uid_map


class Monitor:
    def __init__(self, bot):
        self.bot = bot
        self._running = False
        self._last_hr: dict[str, float] = {}  # key: "guild_id:clan_name"

    def start(self):
        self._running = True
        asyncio.create_task(self._loop())
        print("✅ Monitor gestartet")

    def stop(self):
        self._running = False

    async def _loop(self):
        await self.bot.wait_until_ready()
        async with aiohttp.ClientSession() as s:
            while self._running:
                await self._tick(s)
                await asyncio.sleep(POLL_INTERVAL)

    async def _tick(self, s):
        tracked = db.get_all_tracked()

        # Clan-Daten einmal pro Clan-Name holen
        clan_data_cache: dict[str, dict] = {}
        clan_rank_cache: dict[str, int | None] = {}
        clan_lr_cache:   dict[str, int | None] = {}

        unique_clans = {t["clan_name"] for t in tracked}
        for cn in unique_clans:
            clan_data_cache[cn] = await ps99.get_clan(s, cn)

        # Ranks & League Ranks parallel
        for cn in unique_clans:
            try:
                clan_rank_cache[cn] = await ps99.get_clan_rank(s, cn)
            except Exception:
                clan_rank_cache[cn] = None
            # League rank only for clans with leagues channel set
            needs_lr = any(
                t["channels"].get("leagues") and not t["disabled"].get("leagues")
                for t in tracked if t["clan_name"] == cn
            )
            if needs_lr:
                try:
                    clan_lr_cache[cn] = await ps99.get_clan_league_rank(s, cn)
                except Exception:
                    clan_lr_cache[cn] = None

        for t in tracked:
            try:
                await self._process(
                    s, t,
                    clan_data_cache[t["clan_name"]],
                    clan_rank_cache[t["clan_name"]],
                    clan_lr_cache.get(t["clan_name"]),
                )
            except Exception as ex:
                print(f"❌ Monitor [{t['clan_name']}]: {ex}")

    async def _process(self, s, entry, data, rank_now, league_rank_now):
        if not data:
            return
        cn       = entry["clan_name"]
        gid      = entry["guild_id"]
        channels = entry.get("channels", {})
        disabled = entry.get("disabled", {})

        def get_ch(notif_type: str):
            if disabled.get(notif_type, False):
                return None
            ch_id = channels.get(notif_type, "")
            if not ch_id:
                return None
            return self.bot.get_channel(int(ch_id))

        prev     = db.latest_snapshot(cn)
        pts_now  = ps99.total_points(data)
        hrly_now = ps99.hourly_points(data)
        dia_now  = ps99.deposited_diamonds(data)
        ids_now  = ps99.member_ids(data)
        md_now   = ps99.member_diamonds(data)
        mb_now   = ps99.member_battle_points(data)
        capacity = data.get("MemberCapacity", 75)
        icon     = data.get("Icon", "")

        # ── CW RANK CHANGE ─────────────────────────────────────────
        rank_prev = db.last_rank(cn)
        ch = get_ch("clanrank")
        if ch and rank_now and rank_prev and rank_now != rank_prev:
            buf = await generate_ranking_change(cn, rank_prev, rank_now, pts_now, icon)
            await ch.send(file=discord.File(buf, f"{cn}_ranking.png"))

        # ── JOIN / LEAVE ───────────────────────────────────────────
        ch = get_ch("joinleave")
        if prev and ch:
            prev_ids = set(prev.get("members", []))
            curr_ids = set(ids_now)
            for uid in curr_ids - prev_ids:
                name = await self._name(s, uid)
                buf  = await generate_player_event(name, len(curr_ids), capacity, cn, joined=True)
                await ch.send(file=discord.File(buf, f"{cn}_joined.png"))
            for uid in prev_ids - curr_ids:
                name = await self._name(s, uid)
                buf  = await generate_player_event(name, len(curr_ids), capacity, cn, joined=False)
                await ch.send(file=discord.File(buf, f"{cn}_left.png"))

        # ── DIAMONDS ──────────────────────────────────────────────
        ch = get_ch("diamonds")
        if prev and ch:
            prev_md = prev.get("member_diamonds", {})
            for uid, curr_dia in md_now.items():
                prev_dia = float(prev_md.get(str(uid), 0))
                if curr_dia > prev_dia:
                    delta = curr_dia - prev_dia
                    donor = await self._name(s, uid)
                    buf   = await generate_diamond_update(cn, donor, delta, curr_dia, dia_now, icon)
                    await ch.send(file=discord.File(buf, f"{cn}_diamond.png"))

        # ── HOURLY (mit Roblox-Namen im Bild) ─────────────────────
        hr_key = f"{gid}:{cn}"
        now = time.time()
        if now - self._last_hr.get(hr_key, 0) >= 3600:
            self._last_hr[hr_key] = now
            ch = get_ch("hourlystats")
            if ch:
                diff    = db.hourly_diff(cn)
                uid_map = await _bulk_names(s, data)
                buf     = await generate_clan_board(data, cn, rank_now, hrly_now, diff,
                                                    uid_map=uid_map)
                await ch.send(file=discord.File(buf, f"{cn}_hourly.png"))

        # ── LEAGUES RANK CHANGE ────────────────────────────────────
        ch = get_ch("leagues")
        if ch and league_rank_now is not None:
            lr_prev = db.last_league_rank(cn)
            if lr_prev and league_rank_now != lr_prev:
                went_up = league_rank_now < lr_prev
                delta   = abs(league_rank_now - lr_prev)
                color   = 0x57F287 if went_up else 0xED4245
                arrow   = "📈" if went_up else "📉"
                direction = f"Position {'Increased' if went_up else 'Decreased'} by {delta}"
                e = discord.Embed(
                    title=f"{arrow} {cn} LEAGUES RANKING",
                    color=color,
                )
                e.add_field(
                    name=direction,
                    value=f"**[{cn}]**\n**#{lr_prev}** › **#{league_rank_now}**",
                    inline=False,
                )
                e.timestamp = discord.utils.utcnow()
                await ch.send(embed=e)
            db.save_league_rank(cn, league_rank_now)

        db.push_snapshot(cn, pts_now, rank_now, ids_now, dia_now, md_now, mb_now)
        if rank_now:
            db.save_rank(cn, rank_now)

    async def _name(self, s, uid):
        c = db.cached_name(uid)
        if c:
            return c
        n = await ps99.roblox_name(s, uid) or str(uid)
        db.cache_name(uid, n)
        return n
