"""
cogs/tracking.py
/set   clanrank | diamonds | hourlystats | joinleave | leagues
/disable clanrank | diamonds | hourlystats | joinleave | leagues
/checkperms

Beim ersten /set für einen Clan werden ALLE 4 CW-Channels auf denselben
Channel gesetzt. Spätere /set-Befehle ändern nur noch den jeweiligen Typ.
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

    # ── Helper: Snapshot anlegen falls noch keiner da ─────────────────────────
    @staticmethod
    async def _ensure_snapshot(s, clan_name: str):
        if db.latest_snapshot(clan_name):
            return True
        data = await ps99.get_clan(s, clan_name)
        if not data:
            return False
        rank = await ps99.get_clan_rank(s, clan_name)
        db.push_snapshot(
            clan_name,
            ps99.total_points(data),
            rank,
            ps99.member_ids(data),
            ps99.deposited_diamonds(data),
            ps99.member_diamonds(data),
            ps99.member_battle_points(data),
        )
        if rank:
            db.save_rank(clan_name, rank)
        return True

    @staticmethod
    def _is_first_track(guild_id: str, clan_name: str) -> bool:
        entry = db.get_clan_entry(guild_id, clan_name)
        if entry is None:
            return True
        return not any(v for v in entry.get("channels", {}).values())

    # ══════════════════════════════════════════════════════════════════════════
    # /set – Command Group
    # ══════════════════════════════════════════════════════════════════════════
    set_group = app_commands.Group(name="set", description="Configure tracking channels for a clan")

    async def _set_channel(self, interaction: discord.Interaction,
                            clan: str, channel: discord.TextChannel | None,
                            notif_type: str):
        await interaction.response.defer()
        clan  = clan.strip().upper()
        ch_id = str(channel.id if channel else interaction.channel_id)
        gid   = str(interaction.guild_id)

        async with aiohttp.ClientSession() as s:
            data = await ps99.get_clan(s, clan)
            if not data:
                return await interaction.followup.send(f"❌ Clan **{clan}** not found in PS99!")
            await self._ensure_snapshot(s, clan)

        # First time tracking → set ALL 4 CW channels at once
        if self._is_first_track(gid, clan) and notif_type != "leagues":
            for t in ("clanrank", "diamonds", "hourlystats", "joinleave"):
                db.set_clan_channel(gid, clan, t, ch_id)
            desc = (
                f"All notifications for **{clan}** will be posted in <#{ch_id}>\n"
                f"Use specific `/set` subcommands to route types to different channels."
            )
        else:
            db.set_clan_channel(gid, clan, notif_type, ch_id)
            desc = f"**{notif_type}** notifications for **{clan}** → <#{ch_id}>"

        labels = {
            "clanrank":    "📊 ClanRank",
            "diamonds":    "💎 Diamonds",
            "hourlystats": "⏰ Hourly Stats",
            "joinleave":   "👤 Join/Leave",
            "leagues":     "🏆 Leagues",
        }
        e = discord.Embed(
            title=f"✅ {labels.get(notif_type, notif_type)} set for **{clan}**",
            description=desc,
            color=0x57F287,
        )
        e.add_field(name="⭐ Battle Points", value=fmt(ps99.total_points(data)),        inline=True)
        e.add_field(name="👥 Members",
                    value=f"{len(data.get('Members',[]))}/{data.get('MemberCapacity',75)}",
                    inline=True)
        e.add_field(name="💎 Diamonds",     value=fmt(ps99.deposited_diamonds(data)), inline=True)
        await interaction.followup.send(embed=e)

    @set_group.command(name="clanrank", description="📊 Set the ClanRank notification channel")
    @app_commands.describe(clan="Clan Name (e.g. ZYXE)", channel="Channel (default: current channel)")
    async def set_clanrank(self, interaction: discord.Interaction,
                           clan: str, channel: discord.TextChannel = None):
        await self._set_channel(interaction, clan, channel, "clanrank")

    @set_group.command(name="diamonds", description="💎 Set the Diamond notification channel")
    @app_commands.describe(clan="Clan Name", channel="Channel (default: current channel)")
    async def set_diamonds(self, interaction: discord.Interaction,
                           clan: str, channel: discord.TextChannel = None):
        await self._set_channel(interaction, clan, channel, "diamonds")

    @set_group.command(name="hourlystats", description="⏰ Set the Hourly Stats channel")
    @app_commands.describe(clan="Clan Name", channel="Channel (default: current channel)")
    async def set_hourlystats(self, interaction: discord.Interaction,
                               clan: str, channel: discord.TextChannel = None):
        await self._set_channel(interaction, clan, channel, "hourlystats")

    @set_group.command(name="joinleave", description="👤 Set the Join/Leave notification channel")
    @app_commands.describe(clan="Clan Name", channel="Channel (default: current channel)")
    async def set_joinleave(self, interaction: discord.Interaction,
                             clan: str, channel: discord.TextChannel = None):
        await self._set_channel(interaction, clan, channel, "joinleave")

    @set_group.command(name="leagues", description="🏆 Track a clan's Leagues position")
    @app_commands.describe(clan="Clan Name", channel="Channel (default: current channel)")
    async def set_leagues(self, interaction: discord.Interaction,
                           clan: str, channel: discord.TextChannel = None):
        await self._set_channel(interaction, clan, channel, "leagues")

    # ══════════════════════════════════════════════════════════════════════════
    # /disable – Command Group
    # ══════════════════════════════════════════════════════════════════════════
    disable_group = app_commands.Group(name="disable", description="Disable notifications for a clan")

    async def _disable(self, interaction: discord.Interaction, clan: str, notif_type: str):
        await interaction.response.defer()
        clan = clan.strip().upper()
        ok   = db.disable_notif(str(interaction.guild_id), clan, notif_type)
        if not ok:
            return await interaction.followup.send(
                f"❌ **{clan}** is not tracked. Use `/set {notif_type}` first."
            )
        labels = {
            "clanrank":    "📊 ClanRank",
            "diamonds":    "💎 Diamonds",
            "hourlystats": "⏰ Hourly Stats",
            "joinleave":   "👤 Join/Leave",
            "leagues":     "🏆 Leagues",
        }
        await interaction.followup.send(
            f"❌ **{labels.get(notif_type, notif_type)}** notifications for **{clan}** disabled."
        )

    @disable_group.command(name="clanrank", description="📊 Disable ClanRank for one clan")
    @app_commands.describe(clan="Clan Name")
    async def disable_clanrank(self, i: discord.Interaction, clan: str):
        await self._disable(i, clan, "clanrank")

    @disable_group.command(name="diamonds", description="💎 Disable Diamonds for one clan")
    @app_commands.describe(clan="Clan Name")
    async def disable_diamonds(self, i: discord.Interaction, clan: str):
        await self._disable(i, clan, "diamonds")

    @disable_group.command(name="hourlystats", description="⏰ Disable Hourly Contribution")
    @app_commands.describe(clan="Clan Name")
    async def disable_hourlystats(self, i: discord.Interaction, clan: str):
        await self._disable(i, clan, "hourlystats")

    @disable_group.command(name="joinleave", description="👤 Disable Join/Leave for one clan")
    @app_commands.describe(clan="Clan Name")
    async def disable_joinleave(self, i: discord.Interaction, clan: str):
        await self._disable(i, clan, "joinleave")

    @disable_group.command(name="leagues", description="🏆 Disable Leagues tracking for one clan")
    @app_commands.describe(clan="Clan Name")
    async def disable_leagues(self, i: discord.Interaction, clan: str):
        await self._disable(i, clan, "leagues")

    # ══════════════════════════════════════════════════════════════════════════
    # /checkperms
    # ══════════════════════════════════════════════════════════════════════════
    @app_commands.command(name="checkperms", description="🔐 Checks the permissions of the bot")
    @app_commands.describe(channel="Channel to check (default: current)")
    async def checkperms(self, interaction: discord.Interaction,
                         channel: discord.TextChannel = None):
        await interaction.response.defer()
        ch    = channel or interaction.channel
        perms = ch.permissions_for(interaction.guild.me)
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
    await bot.add_cog(TrackingCog(bot))
