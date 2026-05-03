"""
cogs/clan.py
!cb          – Clan Board (Image)
/search      – Lookup a player's current rank in a clan
/history     – Show a player's historical battle data
/dailystars  – Informations about each Day
/oldcw       – Clanwar Informations from the past
/exist       – Exist Informations (check clan/player)
"""

import discord
from discord.ext import commands
from discord import app_commands
import aiohttp, asyncio
from datetime import datetime, timezone

import api as ps99
import db
from image_gen import generate_clan_board
from fmt import fmt


class ClanCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    # ── !cb ───────────────────────────────────────────────────────────────────
    @commands.command(name="cb")
    async def cb(self, ctx, *, name: str = ""):
        if not name:
            return await ctx.send("❌ `!cb ZYXE`")
        name = name.strip().upper()
        msg  = await ctx.send(f"⏳ Lade **{name}**…")
        try:
            async with aiohttp.ClientSession() as s:
                data, rank = await asyncio.gather(
                    ps99.get_clan(s, name), ps99.get_clan_rank(s, name)
                )
            if not data:
                return await msg.edit(content=f"❌ **{name}** nicht gefunden!")
            buf = await generate_clan_board(data, name, rank,
                                            ps99.hourly_points(data),
                                            db.hourly_diff(name))
            await msg.delete()
            await ctx.send(file=discord.File(buf, filename=f"{name}_board.png"))
        except Exception as e:
            await msg.edit(content=f"❌ Fehler: {e}")

    # ── /search ───────────────────────────────────────────────────────────────
    @app_commands.command(name="search", description="🔍 Lookup a player's current rank in a clan")
    @app_commands.describe(player="Roblox Username", clan="Clan Name")
    async def search(self, interaction: discord.Interaction, player: str, clan: str):
        await interaction.response.defer()
        clan = clan.strip().upper()
        try:
            async with aiohttp.ClientSession() as s:
                uid  = await ps99.roblox_uid(s, player)
                if not uid:
                    return await interaction.followup.send(f"❌ Player **{player}** not found on Roblox!")
                data = await ps99.get_clan(s, clan)
                if not data:
                    return await interaction.followup.send(f"❌ Clan **{clan}** not found!")

            battle = ps99.battle_sorted(data)
            member = next((m for m in battle if m.get("UserID") == uid), None)

            e = discord.Embed(
                title=f"🔍 {player}  •  {clan}",
                color=0x5865F2,
            )
            if member:
                rank_in_clan = battle.index(member) + 1
                e.add_field(name="⭐ Battle Points", value=f"**{fmt(member.get('Points', 0))}**", inline=True)
                e.add_field(name="🏅 Clan Rank",    value=f"**#{rank_in_clan}**",                inline=True)
                e.color = 0x57F287
            else:
                e.description = f"**{player}** has no contributions in **{clan}** yet."
                e.color = 0xED4245

            total = ps99.total_points(data)
            e.add_field(name="📊 Clan Total", value=fmt(total), inline=True)
            e.add_field(name="👥 Members",
                        value=f"{len(data.get('Members', []))}/{data.get('MemberCapacity', 75)}",
                        inline=True)
            e.timestamp = discord.utils.utcnow()
            await interaction.followup.send(embed=e)
        except Exception as ex:
            await interaction.followup.send(f"❌ Error: {ex}")

    # ── /history ──────────────────────────────────────────────────────────────
    @app_commands.command(name="history", description="📈 Show a player's historical battle data")
    @app_commands.describe(player="Roblox Username", clan="Clan Name")
    async def history(self, interaction: discord.Interaction, player: str, clan: str):
        await interaction.response.defer()
        clan = clan.strip().upper()
        try:
            async with aiohttp.ClientSession() as s:
                uid = await ps99.roblox_uid(s, player)
                if not uid:
                    return await interaction.followup.send(f"❌ Player **{player}** not found!")

            snaps = db.get_snapshots(clan, 48)
            if not snaps:
                return await interaction.followup.send(
                    f"❌ No snapshot data for **{clan}**. Use `/set hourlystats` to start tracking."
                )

            uid_str = str(uid)
            lines   = []
            for snap in snaps[:24]:
                mb  = snap.get("member_battle", {})
                pts = mb.get(uid_str, None)
                if pts is None:
                    continue
                ts  = datetime.fromtimestamp(snap["ts"], tz=timezone.utc).strftime("%d.%m %H:%M")
                lines.append(f"`{ts}` ⭐ **{fmt(pts)}**")

            if not lines:
                return await interaction.followup.send(
                    f"❌ No battle data found for **{player}** in **{clan}** snapshots.\n"
                    f"*(Data is recorded per snapshot — player may not have contributed yet.)*"
                )

            e = discord.Embed(
                title=f"📈 History  •  {player}  in  {clan}",
                description="\n".join(lines[:20]),
                color=0xFFD700,
            )
            e.set_footer(text="Snapshot history — last 24 entries with player data")
            e.timestamp = discord.utils.utcnow()
            await interaction.followup.send(embed=e)
        except Exception as ex:
            await interaction.followup.send(f"❌ Error: {ex}")

    # ── /dailystars ───────────────────────────────────────────────────────────
    @app_commands.command(name="dailystars", description="⭐ Informations about each Day's clan stars")
    @app_commands.describe(clan="Clan Name")
    async def dailystars(self, interaction: discord.Interaction, clan: str):
        await interaction.response.defer()
        clan  = clan.strip().upper()
        snaps = db.get_snapshots(clan, 168)  # up to 7 days
        if not snaps:
            return await interaction.followup.send(
                f"❌ No data for **{clan}**. Use `/set hourlystats` to start tracking."
            )

        # Group by UTC day → take max points per day
        from collections import defaultdict
        day_pts: dict[str, list[int]] = defaultdict(list)
        for s in snaps:
            day = datetime.fromtimestamp(s["ts"], tz=timezone.utc).strftime("%d.%m.%Y")
            day_pts[day].append(s["points"])

        # Sorted days (most recent first)
        days = sorted(day_pts.keys(),
                      key=lambda d: datetime.strptime(d, "%d.%m.%Y"),
                      reverse=True)[:7]

        lines = []
        prev_max = None
        for day in days:
            mx = max(day_pts[day])
            mn = min(day_pts[day])
            gained = mx - mn
            lines.append(f"**{day}**  ⭐ +{fmt(gained)}  *(max {fmt(mx)})*")
            prev_max = mx

        e = discord.Embed(
            title=f"⭐ Daily Stars  •  {clan}",
            description="\n".join(lines) or "*No data*",
            color=0xFFD700,
        )
        e.set_footer(text="Stars gained per day based on snapshots")
        e.timestamp = discord.utils.utcnow()
        await interaction.followup.send(embed=e)

    # ── /oldcw ────────────────────────────────────────────────────────────────
    @app_commands.command(name="oldcw", description="📜 Clanwar Informations from the past")
    @app_commands.describe(clan="Clan Name")
    async def oldcw(self, interaction: discord.Interaction, clan: str):
        await interaction.response.defer()
        clan  = clan.strip().upper()
        snaps = db.get_snapshots(clan, 168)
        if not snaps:
            return await interaction.followup.send(
                f"❌ No data for **{clan}**. Use `/set hourlystats` to start tracking."
            )

        newest = snaps[0]
        oldest = snaps[-1]
        duration_h = max(1, (newest["ts"] - oldest["ts"]) // 3600)
        gained     = newest["points"] - oldest["points"]
        avg_h      = gained // duration_h if duration_h else 0

        start_dt = datetime.fromtimestamp(oldest["ts"], tz=timezone.utc).strftime("%d.%m.%Y %H:%M")
        end_dt   = datetime.fromtimestamp(newest["ts"], tz=timezone.utc).strftime("%d.%m.%Y %H:%M")

        e = discord.Embed(
            title=f"📜 Old CW Data  •  {clan}",
            color=0x5865F2,
        )
        e.add_field(name="📅 From",        value=start_dt,            inline=True)
        e.add_field(name="📅 To",          value=end_dt,              inline=True)
        e.add_field(name="⏱️ Duration",    value=f"{duration_h}h",    inline=True)
        e.add_field(name="⭐ Stars gained", value=fmt(gained),         inline=True)
        e.add_field(name="⚡ Avg/h",       value=fmt(avg_h),          inline=True)
        e.add_field(name="📊 Peak Points", value=fmt(newest["points"]),inline=True)
        if newest.get("rank"):
            e.add_field(name="🏅 Last Rank", value=f"#{newest['rank']}", inline=True)
        e.set_footer(text=f"Based on {len(snaps)} snapshots")
        e.timestamp = discord.utils.utcnow()
        await interaction.followup.send(embed=e)

    # ── /exist ────────────────────────────────────────────────────────────────
    @app_commands.command(name="exist", description="✅ Exist Informations — check if a clan or player exists")
    @app_commands.describe(name="Clan name or Roblox username")
    async def exist(self, interaction: discord.Interaction, name: str):
        await interaction.response.defer()
        name_clean = name.strip()
        try:
            async with aiohttp.ClientSession() as s:
                clan_data, uid = await asyncio.gather(
                    ps99.get_clan(s, name_clean.upper()),
                    ps99.roblox_uid(s, name_clean),
                )

            e = discord.Embed(title=f"🔎 Exist Check  •  {name_clean}", color=0x5865F2)
            found = False

            if clan_data:
                found = True
                mc  = len(clan_data.get("Members", []))
                cap = clan_data.get("MemberCapacity", 75)
                e.add_field(name="🏰 Clan", value=f"✅ **{name_clean.upper()}** exists", inline=False)
                e.add_field(name="👥 Members",
                            value=f"{mc}/{cap}", inline=True)
                e.add_field(name="⭐ Battle Points",
                            value=fmt(ps99.total_points(clan_data)), inline=True)
                e.add_field(name="💎 Diamonds",
                            value=fmt(ps99.deposited_diamonds(clan_data)), inline=True)

            if uid:
                found = True
                e.add_field(name="👤 Player",
                            value=f"✅ **{name_clean}** exists on Roblox (UID: `{uid}`)",
                            inline=False)

            if not found:
                e.description = f"❌ **{name_clean}** not found as clan or Roblox player."
                e.color = 0xED4245

            e.timestamp = discord.utils.utcnow()
            await interaction.followup.send(embed=e)
        except Exception as ex:
            await interaction.followup.send(f"❌ Error: {ex}")


async def setup(bot):
    await bot.add_cog(ClanCog(bot))
