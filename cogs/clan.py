"""
cogs/clan.py
Commands:
  !cb <clan>            – großes Dashboard
  /clan <name>          – gleich wie !cb
  /clan_rank <name>     – aktuelle Platzierung
  /clan_stats <name>    – 24h Punkte-Historie
  /top_clans            – Top 10 global
  /contributors <name>  – Top Clanwar Contributors
  /member_stats         – Punkte eines Members
"""

import discord
from discord.ext import commands
from discord import app_commands
import aiohttp
import asyncio
from datetime import datetime

import api  as ps99
import db
import embeds
from fmt import fmt, rank_medal

class ClanCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    # ── helper: fetch clan + rank parallel ────────────────────────────────────
    async def _fetch(self, session, name):
        """Fetch clan data and rank at the same time."""
        data, rank = await asyncio.gather(
            ps99.get_clan(session, name),
            ps99.get_clan_rank(session, name)
        )
        return data, rank

    # ── !cb <clan> ─────────────────────────────────────────────────────────────
    @commands.command(name="cb")
    async def cb_prefix(self, ctx: commands.Context, *, name: str = ""):
        """!cb ZYXE  –  zeigt das große Clan-Dashboard"""
        if not name:
            return await ctx.send("❌ Bitte einen Clan-Namen angeben: `!cb ZYXE`")
        name = name.strip().upper()
        msg  = await ctx.send(f"⏳ Lade Daten für **{name}**…")

        async with aiohttp.ClientSession() as s:
            data, rank = await self._fetch(s, name)
            if not data:
                return await msg.edit(content=f"❌ Clan **{name}** nicht gefunden!")
            hrly = ps99.hourly_points(data)
            diff = db.hourly_diff(name)

        emb = embeds.clan_board(data, name, rank, hrly, diff)
        await msg.edit(content=None, embed=emb)

    # ── /clan ──────────────────────────────────────────────────────────────────
    @app_commands.command(name="clan",
                          description="🏆 Großes Clan-Dashboard (Rang, Punkte, alle Members)")
    @app_commands.describe(name="Clan Name (z.B. ZYXE)")
    async def clan_slash(self, interaction: discord.Interaction, name: str):
        await interaction.response.defer()
        name = name.strip().upper()
        async with aiohttp.ClientSession() as s:
            data, rank = await self._fetch(s, name)
            if not data:
                return await interaction.followup.send(f"❌ Clan **{name}** nicht gefunden!")
            hrly = ps99.hourly_points(data)
            diff = db.hourly_diff(name)

        emb = embeds.clan_board(data, name, rank, hrly, diff)
        await interaction.followup.send(embed=emb)

    # ── /clan_rank ─────────────────────────────────────────────────────────────
    @app_commands.command(name="clan_rank",
                          description="🥇 Aktuelle Platzierung eines Clans im Leaderboard")
    @app_commands.describe(name="Clan Name")
    async def clan_rank(self, interaction: discord.Interaction, name: str):
        await interaction.response.defer()
        name = name.strip().upper()
        async with aiohttp.ClientSession() as s:
            data, rank = await self._fetch(s, name)
            if not data:
                return await interaction.followup.send(f"❌ Clan **{name}** nicht gefunden!")
            pts = ps99.total_points(data)

        prev_rank = db.last_rank(name)
        change = ""
        if prev_rank and rank:
            d = prev_rank - rank
            if d > 0:   change = f"  📈 +{d}"
            elif d < 0: change = f"  📉 {d}"

        e = discord.Embed(title=f"🏅 Platzierung  •  {name}", color=0xFFD700)
        e.add_field(name="Rank",   value=f"**#{rank}**{change}" if rank else "**?**", inline=True)
        e.add_field(name="Punkte", value=f"**{fmt(pts)}**", inline=True)
        e.timestamp = discord.utils.utcnow()
        await interaction.followup.send(embed=e)

    # ── /clan_stats ────────────────────────────────────────────────────────────
    @app_commands.command(name="clan_stats",
                          description="📊 Stündliche Punkte-Geschichte der letzten 24h")
    @app_commands.describe(name="Clan Name")
    async def clan_stats(self, interaction: discord.Interaction, name: str):
        await interaction.response.defer()
        name  = name.strip().upper()
        snaps = db.get_snapshots(name, 24)
        if not snaps:
            return await interaction.followup.send(
                f"❌ Keine Daten für **{name}**. Bitte zuerst `/clan_track` nutzen!"
            )

        lines = []
        for i, s in enumerate(snaps[:12]):
            prev = snaps[i + 1] if i + 1 < len(snaps) else None
            diff = s["points"] - prev["points"] if prev else 0
            ts   = datetime.fromtimestamp(s["ts"]).strftime("%H:%M")
            sign = "+" if diff >= 0 else ""
            lines.append(f"`{ts}` **{fmt(s['points'])}** pts `({sign}{fmt(diff)}/h)`")

        latest = snaps[0]
        oldest = snaps[-1]
        avg    = int((latest["points"] - oldest["points"]) / max(1, len(snaps) - 1))

        e = discord.Embed(title=f"📊 Hourly Stats  •  {name}",
                          description="\n".join(lines), color=0xFFD700)
        e.add_field(name="⚡ Ø /Stunde",  value=f"**{fmt(avg)}**", inline=True)
        e.add_field(name="📈 Gesamt 24h",
                    value=f"**+{fmt(max(0, latest['points']-oldest['points']))}**", inline=True)
        e.set_footer(text="Letzte 24 Stunden")
        e.timestamp = discord.utils.utcnow()
        await interaction.followup.send(embed=e)

    # ── /top_clans ─────────────────────────────────────────────────────────────
    @app_commands.command(name="top_clans",
                          description="🏅 Top 10 Clans im globalen PS99 Leaderboard")
    async def top_clans(self, interaction: discord.Interaction):
        await interaction.response.defer()
        async with aiohttp.ClientSession() as s:
            clans = await ps99.get_top_clans(s, 10)
        if not clans:
            return await interaction.followup.send("❌ API nicht erreichbar.")

        lines = [
            f"{rank_medal(i)} **{c.get('Name','?')}**  —  "
            f"{fmt(c.get('Points',0))} pts  •  "
            f"{c.get('Members',0)}/{c.get('MemberCapacity',75)} Members"
            for i, c in enumerate(clans)
        ]
        e = discord.Embed(title="🏆 Top 10 Clans  —  PS99 Global",
                          description="\n".join(lines), color=0xFFD700)
        e.set_footer(text="Daten von ps99.biggamesapi.io")
        e.timestamp = discord.utils.utcnow()
        await interaction.followup.send(embed=e)

    # ── /contributors ──────────────────────────────────────────────────────────
    @app_commands.command(name="contributors",
                          description="⭐ Top Clanwar Contributors")
    @app_commands.describe(name="Clan Name")
    async def contributors(self, interaction: discord.Interaction, name: str):
        await interaction.response.defer()
        name = name.strip().upper()
        async with aiohttp.ClientSession() as s:
            data, rank = await self._fetch(s, name)
            if not data:
                return await interaction.followup.send(f"❌ Clan **{name}** nicht gefunden!")
            battle_info = await ps99.get_active_clan_battle(s)

            # Resolve top-10 names
            top10_ids = [m["UserID"] for m in ps99.battle_sorted(data)[:10]]
            uid_map   = await ps99.roblox_names_bulk(s, top10_ids)

        for uid, uname in uid_map.items():
            db.cache_name(uid, uname)

        battle_name  = (battle_info or {}).get("configName", "ClanBattle")
        battle_sorted = ps99.battle_sorted(data)
        total_pts    = ps99.total_points(data)
        kick_cd      = data.get("LastKickTimestamp")
        kick_str     = f"<t:{kick_cd}:R>" if kick_cd else "–"
        member_count = len(data.get("Members", []))
        capacity     = data.get("MemberCapacity", 75)

        lines = []
        for i, m in enumerate(battle_sorted[:10]):
            uid  = m.get("UserID", "?")
            n    = uid_map.get(uid) or db.cached_name(uid) or f"UserID {uid}"
            pts  = m.get("Points", 0)
            lines.append(f"**{i+1}.** {n} ⭐ **{fmt(pts)}**")

        e = discord.Embed(title=f"⭐ Top Contributors  •  {name}", color=0xFFD700)
        e.add_field(name="Current Event",  value=f"**{battle_name}**",               inline=True)
        e.add_field(name="Current Rank",   value=f"**#{rank}**" if rank else "**?**", inline=True)
        e.add_field(name="Total Stars",    value=f"**{fmt(total_pts)}** ⭐",           inline=True)
        e.add_field(name="Kick Cooldown",  value=kick_str,                             inline=True)
        e.add_field(name="Members",        value=f"**{member_count}/{capacity}**",     inline=True)
        e.add_field(name="\u200b",         value="\n".join(lines) or "*–*",            inline=False)
        e.set_footer(text=f"PS99 ClanWar Bot  •  {name}")
        e.timestamp = discord.utils.utcnow()
        await interaction.followup.send(embed=e)

    # ── /member_stats ──────────────────────────────────────────────────────────
    @app_commands.command(name="member_stats",
                          description="👤 Punkte eines Members in einem Clan")
    @app_commands.describe(clan="Clan Name", roblox_user="Roblox Username")
    async def member_stats(self, interaction: discord.Interaction,
                           clan: str, roblox_user: str):
        await interaction.response.defer()
        clan = clan.strip().upper()
        async with aiohttp.ClientSession() as s:
            data = await ps99.get_clan(s, clan)
            if not data:
                return await interaction.followup.send(f"❌ Clan **{clan}** nicht gefunden!")
            uid = await ps99.roblox_uid(s, roblox_user)
        if not uid:
            return await interaction.followup.send(
                f"❌ Roblox-User **{roblox_user}** nicht gefunden!"
            )

        battle = ps99.battle_sorted(data)
        member = next((m for m in battle if m["UserID"] == uid), None)
        if not member:
            return await interaction.followup.send(
                f"❌ **{roblox_user}** hat keine Punkte in **{clan}**."
            )
        rank_in_clan = battle.index(member) + 1

        e = discord.Embed(title=f"👤 {roblox_user}  •  {clan}", color=0x5865F2)
        e.add_field(name="📊 Punkte",    value=f"**{fmt(member.get('Points',0))}**", inline=True)
        e.add_field(name="🏅 Clan-Rang", value=f"**#{rank_in_clan}**",               inline=True)
        e.timestamp = discord.utils.utcnow()
        await interaction.followup.send(embed=e)


async def setup(bot):
    await bot.add_cog(ClanCog(bot))