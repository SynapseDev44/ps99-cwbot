"""monitor.py – Pull → Save → Compare, sendet Bilder statt Embeds"""
import asyncio, time
import aiohttp
import api as ps99
import db
from image_gen import (generate_diamond_update, generate_ranking_change,
                        generate_player_event, generate_clan_board)
import discord
from config import POLL_INTERVAL

class Monitor:
    def __init__(self, bot):
        self.bot=bot; self._running=False; self._last_hr: dict[str,float]={}

    def start(self):
        self._running=True
        asyncio.create_task(self._loop())
        print("✅ Monitor gestartet")

    def stop(self): self._running=False

    async def _loop(self):
        await self.bot.wait_until_ready()
        async with aiohttp.ClientSession() as s:
            while self._running:
                await self._tick(s)
                await asyncio.sleep(POLL_INTERVAL)

    async def _tick(self, s):
        tracked=db.get_all_tracked()
        cache={}
        for t in tracked:
            cn=t["clan_name"]
            if cn not in cache:
                cache[cn]=await ps99.get_clan(s,cn)
        for t in tracked:
            try: await self._process(s, t, cache[t["clan_name"]])
            except Exception as ex: print(f"❌ Monitor [{t['clan_name']}]: {ex}")

    async def _process(self, s, entry, data):
        if not data: return
        cn       = entry["clan_name"]
        notifs   = entry.get("notifs",{})
        channel  = self.bot.get_channel(int(entry["channel_id"]))
        prev     = db.latest_snapshot(cn)
        pts_now  = ps99.total_points(data)
        hrly_now = ps99.hourly_points(data)
        dia_now  = ps99.deposited_diamonds(data)
        ids_now  = ps99.member_ids(data)
        capacity = data.get("MemberCapacity",75)
        icon     = data.get("Icon","")

        # ── RANK ──────────────────────────────────────────────
        rank_now  = await ps99.get_clan_rank(s, cn)
        rank_prev = db.last_rank(cn)
        if channel and notifs.get("ranking",True):
            if rank_now and rank_prev and rank_now!=rank_prev:
                buf = await generate_ranking_change(cn, rank_prev, rank_now, pts_now, icon)
                await channel.send(file=discord.File(buf, f"{cn}_ranking.png"))

        # ── JOIN / LEAVE ──────────────────────────────────────
        if prev and channel and notifs.get("join_leave",True):
            prev_ids=set(prev.get("members",[])); curr_ids=set(ids_now)
            for uid in curr_ids-prev_ids:
                name=await self._name(s,uid)
                buf=await generate_player_event(name,len(curr_ids),capacity,cn,joined=True)
                await channel.send(file=discord.File(buf, f"{cn}_joined.png"))
            for uid in prev_ids-curr_ids:
                name=await self._name(s,uid)
                buf=await generate_player_event(name,len(curr_ids),capacity,cn,joined=False)
                await channel.send(file=discord.File(buf, f"{cn}_left.png"))

        # ── DIAMONDS ──────────────────────────────────────────
        if prev and channel and notifs.get("diamond",True):
            prev_dia=prev.get("diamonds",0)
            if dia_now>prev_dia:
                delta=dia_now-prev_dia
                buf=await generate_diamond_update(cn,"?",delta,delta,dia_now,icon)
                await channel.send(file=discord.File(buf, f"{cn}_diamond.png"))

        # ── HOURLY ────────────────────────────────────────────
        now=time.time()
        if now-self._last_hr.get(cn,0)>=3600:
            self._last_hr[cn]=now
            if channel and notifs.get("hourly",True):
                diff=db.hourly_diff(cn)
                buf=await generate_clan_board(data,cn,rank_now,hrly_now,diff)
                await channel.send(file=discord.File(buf, f"{cn}_hourly.png"))

        db.push_snapshot(cn,pts_now,rank_now,ids_now,dia_now)
        if rank_now: db.save_rank(cn,rank_now)

    async def _name(self,s,uid):
        c=db.cached_name(uid)
        if c: return c
        n=await ps99.roblox_name(s,uid) or str(uid)
        db.cache_name(uid,n); return n
