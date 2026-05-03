"""cogs/clan.py – !cb, /clan, /contributors, /clan_rank, /clan_stats, /top_clans, /member_stats"""
import discord
from discord.ext import commands
from discord import app_commands
import aiohttp, asyncio
from datetime import datetime

import api as ps99
import db, embeds
from image_gen import generate_clan_board, generate_top_contributors
from fmt import fmt, rank_medal

class ClanCog(commands.Cog):
    def __init__(self, bot): self.bot = bot

    @staticmethod
    async def _fetch(s, name):
        return await asyncio.gather(ps99.get_clan(s, name), ps99.get_clan_rank(s, name))

    # ── !cb ──────────────────────────────────────────────────────
    @commands.command(name="cb")
    async def cb(self, ctx, *, name: str = ""):
        if not name: return await ctx.send("❌ `!cb ZYXE`")
        name = name.strip().upper()
        msg  = await ctx.send(f"⏳ Lade **{name}**…")
        try:
            async with aiohttp.ClientSession() as s:
                data, rank = await self._fetch(s, name)
            if not data: return await msg.edit(content=f"❌ **{name}** nicht gefunden!")
            buf = await generate_clan_board(data, name, rank,
                                            ps99.hourly_points(data),
                                            db.hourly_diff(name))
            await msg.delete()
            await ctx.send(file=discord.File(buf, filename=f"{name}_board.png"))
        except Exception as e:
            await msg.edit(content=f"❌ Fehler: {e}")

    # ── /clan ─────────────────────────────────────────────────────
    @app_commands.command(name="clan", description="🏆 Clan-Dashboard als Bild")
    @app_commands.describe(name="Clan Name (z.B. ZYXE)")
    async def clan_slash(self, interaction: discord.Interaction, name: str):
        await interaction.response.defer()
        name = name.strip().upper()
        try:
            async with aiohttp.ClientSession() as s:
                data, rank = await self._fetch(s, name)
            if not data: return await interaction.followup.send(f"❌ **{name}** nicht gefunden!")
            buf = await generate_clan_board(data, name, rank,
                                            ps99.hourly_points(data),
                                            db.hourly_diff(name))
            await interaction.followup.send(file=discord.File(buf, filename=f"{name}_board.png"))
        except Exception as e:
            await interaction.followup.send(f"❌ Fehler: {e}")

    # ── /contributors ─────────────────────────────────────────────
    @app_commands.command(name="contributors", description="⭐ Top Clanwar Contributors")
    @app_commands.describe(name="Clan Name")
    async def contributors(self, interaction: discord.Interaction, name: str):
        await interaction.response.defer()
        name = name.strip().upper()
        try:
            async with aiohttp.ClientSession() as s:
                data, rank  = await self._fetch(s, name)
                if not data: return await interaction.followup.send(f"❌ **{name}** nicht gefunden!")
                battle_info = await ps99.get_active_clan_battle(s)
                top10_ids   = [m["UserID"] for m in ps99.battle_sorted(data)[:10]]
                uid_map     = await ps99.roblox_names_bulk(s, top10_ids)
            for uid, uname in uid_map.items(): db.cache_name(uid, uname)
            full_map = {m["UserID"]: db.cached_name(m["UserID"]) or f"UserID {m['UserID']}"
                        for m in ps99.battle_sorted(data)[:10]}
            bname = (battle_info or {}).get("configName", "ClanBattle")
            buf = await generate_top_contributors(data, name, rank, bname, full_map,
                                                   data.get("Icon",""),
                                                   battle_info=battle_info)
            await interaction.followup.send(file=discord.File(buf, filename=f"{name}_contributors.png"))
        except Exception as e:
            await interaction.followup.send(f"❌ Fehler: {e}")

    # ── /clan_rank ────────────────────────────────────────────────
    @app_commands.command(name="clan_rank", description="🥇 Platzierung eines Clans")
    @app_commands.describe(name="Clan Name")
    async def clan_rank(self, interaction: discord.Interaction, name: str):
        await interaction.response.defer()
        name = name.strip().upper()
        try:
            async with aiohttp.ClientSession() as s:
                data, rank = await self._fetch(s, name)
            if not data: return await interaction.followup.send(f"❌ **{name}** nicht gefunden!")
            prev   = db.last_rank(name)
            change = ""
            if prev and rank:
                d = prev - rank
                change = f"  📈 +{d}" if d>0 else (f"  📉 {d}" if d<0 else "")
            e = discord.Embed(title=f"🏅 {name}", color=0xFFD700)
            e.add_field(name="Rank",   value=f"**#{rank}**{change}" if rank else "**?**", inline=True)
            e.add_field(name="Punkte", value=f"**{fmt(ps99.total_points(data))}**",        inline=True)
            e.timestamp = discord.utils.utcnow()
            await interaction.followup.send(embed=e)
        except Exception as e:
            await interaction.followup.send(f"❌ Fehler: {e}")

    # ── /clan_stats ───────────────────────────────────────────────
    @app_commands.command(name="clan_stats", description="📊 Stündliche Stats")
    @app_commands.describe(name="Clan Name")
    async def clan_stats(self, interaction: discord.Interaction, name: str):
        await interaction.response.defer()
        name  = name.strip().upper()
        snaps = db.get_snapshots(name, 24)
        if not snaps:
            return await interaction.followup.send(f"❌ Keine Daten für **{name}**. Zuerst `/clan_track`!")
        lines = []
        for i, s in enumerate(snaps[:12]):
            prev = snaps[i+1] if i+1<len(snaps) else None
            diff = s["points"]-prev["points"] if prev else 0
            ts   = datetime.fromtimestamp(s["ts"]).strftime("%H:%M")
            sign = "+" if diff>=0 else ""
            lines.append(f"`{ts}` **{fmt(s['points'])}** `({sign}{fmt(diff)}/h)`")
        latest, oldest = snaps[0], snaps[-1]
        avg = int((latest["points"]-oldest["points"]) / max(1,len(snaps)-1))
        e = discord.Embed(title=f"📊 Stats  •  {name}", description="\n".join(lines), color=0xFFD700)
        e.add_field(name="⚡ Ø /h",  value=f"**{fmt(avg)}**", inline=True)
        e.add_field(name="📈 24h",   value=f"**+{fmt(max(0,latest['points']-oldest['points']))}**", inline=True)
        e.timestamp = discord.utils.utcnow()
        await interaction.followup.send(embed=e)

    # ── /top_clans ────────────────────────────────────────────────
    @app_commands.command(name="top_clans", description="🏅 Top 10 Clans global")
    async def top_clans(self, interaction: discord.Interaction):
        await interaction.response.defer()
        try:
            async with aiohttp.ClientSession() as s:
                clans = await ps99.get_top_clans(s, 10)
            if not clans: return await interaction.followup.send("❌ API nicht erreichbar.")
            lines = [f"{rank_medal(i)} **{c.get('Name','?')}** — {fmt(c.get('Points',0))} pts • {c.get('Members',0)}/{c.get('MemberCapacity',75)}"
                     for i,c in enumerate(clans)]
            e = discord.Embed(title="🏆 Top 10 — PS99 Global", description="\n".join(lines), color=0xFFD700)
            e.set_footer(text="ps99.biggamesapi.io")
            e.timestamp = discord.utils.utcnow()
            await interaction.followup.send(embed=e)
        except Exception as e:
            await interaction.followup.send(f"❌ Fehler: {e}")

    # ── /member_stats ─────────────────────────────────────────────
    @app_commands.command(name="member_stats", description="👤 Punkte eines Members")
    @app_commands.describe(clan="Clan Name", roblox_user="Roblox Username")
    async def member_stats(self, interaction: discord.Interaction, clan: str, roblox_user: str):
        await interaction.response.defer()
        clan = clan.strip().upper()
        try:
            async with aiohttp.ClientSession() as s:
                data = await ps99.get_clan(s, clan)
                if not data: return await interaction.followup.send(f"❌ **{clan}** nicht gefunden!")
                uid = await ps99.roblox_uid(s, roblox_user)
            if not uid: return await interaction.followup.send(f"❌ **{roblox_user}** nicht gefunden!")
            battle = ps99.battle_sorted(data)
            member = next((m for m in battle if m["UserID"]==uid), None)
            if not member: return await interaction.followup.send(f"❌ **{roblox_user}** hat keine Punkte in **{clan}**.")
            e = discord.Embed(title=f"👤 {roblox_user}  •  {clan}", color=0x5865F2)
            e.add_field(name="Punkte",    value=f"**{fmt(member.get('Points',0))}**", inline=True)
            e.add_field(name="Clan-Rang", value=f"**#{battle.index(member)+1}**",     inline=True)
            e.timestamp = discord.utils.utcnow()
            await interaction.followup.send(embed=e)
        except Exception as ex:
            await interaction.followup.send(f"❌ Fehler: {ex}")

async def setup(bot):
    await bot.add_cog(ClanCog(bot))
