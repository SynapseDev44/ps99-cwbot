"""
cogs/tracking.py
/set   clanrank | diamonds | hourlystats | joinleave
/disable clanrank | diamonds | hourlystats | joinleave
/checkperms
"""

import discord
from discord.ext import commands
from discord import app_commands
import aiohttp

import api as ps99
import db
from fmt import fmt


class TrackingCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    # ── Helper: ersten Snapshot anlegen falls noch keiner da ──────────────────
    @staticmethod
    async def _ensure_snapshot(s, clan_name: str):
        if db.latest_snapshot(clan_name):
            return True
        data = await ps99.get_clan(s, clan_name)
        if not data:
            return False
        rank = await ps99.get_clan_rank(s, clan_name)
        pts  = ps99.total_points(data)
        ids  = ps99.member_ids(data)
        dia  = ps99.deposited_diamonds(data)
        md   = ps99.member_diamonds(data)
        mb   = ps99.member_battle_points(data)
        db.push_snapshot(clan_name, pts, rank, ids, dia, md, mb)
        if rank:
            db.save_rank(clan_name, rank)
        return True

    # ══════════════════════════════════════════════════════════════════════════
    # /set  –  Command Group
    # ══════════════════════════════════════════════════════════════════════════
    set_group = app_commands.Group(name="set", description="Configure tracking channels for a clan")

    @set_group.command(name="clanrank", description="📊 Set the ClanRank notification channel")
    @app_commands.describe(clan="Clan Name (e.g. ZYXE)", channel="Channel (default: current)")
    async def set_clanrank(self, interaction: discord.Interaction,
                           clan: str, channel: discord.TextChannel = None):
        await interaction.response.defer()
        clan  = clan.strip().upper()
        ch_id = str(channel.id if channel else interaction.channel_id)
        async with aiohttp.ClientSession() as s:
            data = await ps99.get_clan(s, clan)
            if not data:
                return await interaction.followup.send(f"❌ Clan **{clan}** not found in PS99!")
            await self._ensure_snapshot(s, clan)
        db.set_clan_channel(str(interaction.guild_id), clan, "clanrank", ch_id)
        e = discord.Embed(title=f"✅ ClanRank tracking set for **{clan}**", color=0x57F287)
        e.description = f"Rank changes will be posted in <#{ch_id}>"
        e.add_field(name="📊 Points",  value=fmt(ps99.total_points(data)), inline=True)
        e.add_field(name="👥 Members", value=str(len(data.get("Members", []))), inline=True)
        await interaction.followup.send(embed=e)

    @set_group.command(name="diamonds", description="💎 Set the Diamond notification channel")
    @app_commands.describe(clan="Clan Name", channel="Channel (default: current)")
    async def set_diamonds(self, interaction: discord.Interaction,
                           clan: str, channel: discord.TextChannel = None):
        await interaction.response.defer()
        clan  = clan.strip().upper()
        ch_id = str(channel.id if channel else interaction.channel_id)
        async with aiohttp.ClientSession() as s:
            data = await ps99.get_clan(s, clan)
            if not data:
                return await interaction.followup.send(f"❌ Clan **{clan}** not found!")
            await self._ensure_snapshot(s, clan)
        db.set_clan_channel(str(interaction.guild_id), clan, "diamonds", ch_id)
        e = discord.Embed(title=f"✅ Diamonds tracking set for **{clan}**", color=0x57F287)
        e.description = f"Diamond donations will be posted in <#{ch_id}>"
        e.add_field(name="💎 Clan Diamonds", value=fmt(ps99.deposited_diamonds(data)), inline=True)
        await interaction.followup.send(embed=e)

    @set_group.command(name="hourlystats", description="⏰ Set the Hourly Stats channel")
    @app_commands.describe(clan="Clan Name", channel="Channel (default: current)")
    async def set_hourlystats(self, interaction: discord.Interaction,
                               clan: str, channel: discord.TextChannel = None):
        await interaction.response.defer()
        clan  = clan.strip().upper()
        ch_id = str(channel.id if channel else interaction.channel_id)
        async with aiohttp.ClientSession() as s:
            data = await ps99.get_clan(s, clan)
            if not data:
                return await interaction.followup.send(f"❌ Clan **{clan}** not found!")
            await self._ensure_snapshot(s, clan)
        db.set_clan_channel(str(interaction.guild_id), clan, "hourlystats", ch_id)
        e = discord.Embed(title=f"✅ Hourly Stats set for **{clan}**", color=0x57F287)
        e.description = f"Hourly updates will be posted in <#{ch_id}>"
        await interaction.followup.send(embed=e)

    @set_group.command(name="joinleave", description="👤 Set the Join/Leave notification channel")
    @app_commands.describe(clan="Clan Name", channel="Channel (default: current)")
    async def set_joinleave(self, interaction: discord.Interaction,
                             clan: str, channel: discord.TextChannel = None):
        await interaction.response.defer()
        clan  = clan.strip().upper()
        ch_id = str(channel.id if channel else interaction.channel_id)
        async with aiohttp.ClientSession() as s:
            data = await ps99.get_clan(s, clan)
            if not data:
                return await interaction.followup.send(f"❌ Clan **{clan}** not found!")
            await self._ensure_snapshot(s, clan)
        db.set_clan_channel(str(interaction.guild_id), clan, "joinleave", ch_id)
        e = discord.Embed(title=f"✅ Join/Leave set for **{clan}**", color=0x57F287)
        e.description = f"Join/Leave events will be posted in <#{ch_id}>"
        e.add_field(name="👥 Members",
                    value=f"{len(data.get('Members', []))}/{data.get('MemberCapacity', 75)}",
                    inline=True)
        await interaction.followup.send(embed=e)

    # ══════════════════════════════════════════════════════════════════════════
    # /disable  –  Command Group
    # ══════════════════════════════════════════════════════════════════════════
    disable_group = app_commands.Group(name="disable", description="Disable specific notifications for a clan")

    @disable_group.command(name="clanrank", description="📊 Disable ClanRank notifications for one clan")
    @app_commands.describe(clan="Clan Name")
    async def disable_clanrank(self, interaction: discord.Interaction, clan: str):
        await interaction.response.defer()
        clan = clan.strip().upper()
        ok   = db.disable_notif(str(interaction.guild_id), clan, "clanrank")
        if not ok:
            return await interaction.followup.send(f"❌ **{clan}** is not tracked. Use `/set clanrank` first.")
        await interaction.followup.send(f"❌ **ClanRank** notifications for **{clan}** disabled.")

    @disable_group.command(name="diamonds", description="💎 Disable Diamond notifications for one clan")
    @app_commands.describe(clan="Clan Name")
    async def disable_diamonds(self, interaction: discord.Interaction, clan: str):
        await interaction.response.defer()
        clan = clan.strip().upper()
        ok   = db.disable_notif(str(interaction.guild_id), clan, "diamonds")
        if not ok:
            return await interaction.followup.send(f"❌ **{clan}** is not tracked. Use `/set diamonds` first.")
        await interaction.followup.send(f"❌ **Diamonds** notifications for **{clan}** disabled.")

    @disable_group.command(name="hourlystats", description="⏰ Disable Hourly Contribution for one clan")
    @app_commands.describe(clan="Clan Name")
    async def disable_hourlystats(self, interaction: discord.Interaction, clan: str):
        await interaction.response.defer()
        clan = clan.strip().upper()
        ok   = db.disable_notif(str(interaction.guild_id), clan, "hourlystats")
        if not ok:
            return await interaction.followup.send(f"❌ **{clan}** is not tracked. Use `/set hourlystats` first.")
        await interaction.followup.send(f"❌ **Hourly Stats** for **{clan}** disabled.")

    @disable_group.command(name="joinleave", description="👤 Disable Join/Leave for one clan")
    @app_commands.describe(clan="Clan Name")
    async def disable_joinleave(self, interaction: discord.Interaction, clan: str):
        await interaction.response.defer()
        clan = clan.strip().upper()
        ok   = db.disable_notif(str(interaction.guild_id), clan, "joinleave")
        if not ok:
            return await interaction.followup.send(f"❌ **{clan}** is not tracked. Use `/set joinleave` first.")
        await interaction.followup.send(f"❌ **Join/Leave** for **{clan}** disabled.")

    # ══════════════════════════════════════════════════════════════════════════
    # /checkperms
    # ══════════════════════════════════════════════════════════════════════════
    @app_commands.command(name="checkperms", description="🔐 Checks the permissions of the bot in a channel")
    @app_commands.describe(channel="Channel to check (default: current)")
    async def checkperms(self, interaction: discord.Interaction,
                         channel: discord.TextChannel = None):
        await interaction.response.defer()
        ch   = channel or interaction.channel
        me   = interaction.guild.me
        perms = ch.permissions_for(me)
        checks = [
            ("Send Messages",        perms.send_messages),
            ("Embed Links",          perms.embed_links),
            ("Attach Files",         perms.attach_files),
            ("Read Message History", perms.read_message_history),
            ("Add Reactions",        perms.add_reactions),
            ("Use External Emojis",  perms.use_external_emojis),
            ("Manage Messages",      perms.manage_messages),
        ]
        lines  = [f"{'✅' if ok else '❌'} **{name}**" for name, ok in checks]
        all_ok = all(ok for _, ok in checks)
        e = discord.Embed(
            title=f"{'✅' if all_ok else '⚠️'} Bot Permissions in #{ch.name}",
            description="\n".join(lines),
            color=0x57F287 if all_ok else 0xED4245,
        )
        await interaction.followup.send(embed=e)


async def setup(bot):
    cog = TrackingCog(bot)
    await bot.add_cog(cog)
