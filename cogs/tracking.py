"""
cogs/tracking.py
Slash Commands:
  /clan_track     – Clan zu Server hinzufügen
  /clan_untrack   – Clan entfernen
  /clan_list      – Alle getracken Clans
  /notif_toggle   – Benachrichtigung AN/AUS
  /notif_status   – Übersicht aller Einstellungen
"""

import discord
from discord.ext import commands
from discord import app_commands
import aiohttp

import api  as ps99
import db
import embeds
from fmt import fmt

class TrackingCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    # ── /clan_track ────────────────────────────────────────────────────────────
    @app_commands.command(name="clan_track",
                          description="📡 Startet das Tracking eines PS99 Clans")
    @app_commands.describe(
        name    = "Clan Name (z.B. ZYXE)",
        channel = "Channel für Updates (Standard: aktueller Channel)"
    )
    async def clan_track(self, interaction: discord.Interaction,
                         name: str,
                         channel: discord.TextChannel = None):
        await interaction.response.defer()
        name  = name.strip().upper()
        ch_id = str(channel.id) if channel else str(interaction.channel_id)

        async with aiohttp.ClientSession() as s:
            data = await ps99.get_clan(s, name)
            if not data:
                return await interaction.followup.send(
                    f"❌ Clan **{name}** wurde nicht in PS99 gefunden!"
                )
            rank     = await ps99.get_clan_rank(s, name)
            pts      = ps99.total_points(data)
            diamonds = ps99.deposited_diamonds(data)
            ids      = ps99.member_ids(data)

        db.track_clan(str(interaction.guild_id), name, ch_id)
        db.push_snapshot(name, pts, rank, ids, diamonds)
        if rank:
            db.save_rank(name, rank)

        e = discord.Embed(title=f"✅ {name} wird jetzt getrackt!", color=0x57F287)
        e.description = f"Stündliche Updates, Rank-Änderungen, Join/Leave und Diamond-Donations werden in <#{ch_id}> gesendet."
        e.add_field(name="📊 Punkte",    value=fmt(pts),          inline=True)
        e.add_field(name="🥇 Rank",      value=f"#{rank}" if rank else "?", inline=True)
        e.add_field(name="👥 Members",   value=str(len(ids)),     inline=True)
        e.add_field(name="💎 Diamonds",  value=fmt(diamonds),     inline=True)
        e.timestamp = discord.utils.utcnow()
        await interaction.followup.send(embed=e)

    # ── /clan_untrack ──────────────────────────────────────────────────────────
    @app_commands.command(name="clan_untrack",
                          description="❌ Stoppt das Tracking eines Clans")
    @app_commands.describe(name="Clan Name")
    async def clan_untrack(self, interaction: discord.Interaction, name: str):
        await interaction.response.defer()
        name = name.strip().upper()
        if db.untrack_clan(str(interaction.guild_id), name):
            await interaction.followup.send(f"✅ Tracking für **{name}** gestoppt.")
        else:
            await interaction.followup.send(f"❌ **{name}** wird in diesem Server nicht getrackt.")

    # ── /clan_list ─────────────────────────────────────────────────────────────
    @app_commands.command(name="clan_list",
                          description="📋 Alle getracken Clans dieses Servers")
    async def clan_list(self, interaction: discord.Interaction):
        await interaction.response.defer()
        clans = db.get_server_clans(str(interaction.guild_id))
        if not clans:
            return await interaction.followup.send(
                "❌ Keine Clans getrackt. Nutze `/clan_track`!"
            )
        lines = [f"• **{n}** → <#{v['channel_id']}>" for n, v in clans.items()]
        e = discord.Embed(title="📋 Getrackte Clans",
                          description="\n".join(lines),
                          color=0x5865F2)
        e.timestamp = discord.utils.utcnow()
        await interaction.followup.send(embed=e)

    # ── /notif_toggle ──────────────────────────────────────────────────────────
    @app_commands.command(name="notif_toggle",
                          description="🔔 Benachrichtigung für einen Clan AN oder AUS schalten")
    @app_commands.describe(
        clan    = "Clan Name",
        typ     = "Welche Benachrichtigung?",
        enabled = "True = AN  |  False = AUS"
    )
    @app_commands.choices(typ=[
        app_commands.Choice(name="💎 Diamond Donations",    value="diamond"),
        app_commands.Choice(name="👤 Join / Leave",          value="join_leave"),
        app_commands.Choice(name="📊 Ranking Changes",       value="ranking"),
        app_commands.Choice(name="⏰ Stündliche Updates",    value="hourly"),
    ])
    async def notif_toggle(self, interaction: discord.Interaction,
                           clan: str, typ: str, enabled: bool):
        await interaction.response.defer()
        clan = clan.strip().upper()
        ok   = db.set_notif(str(interaction.guild_id), clan, typ, enabled)
        if not ok:
            return await interaction.followup.send(
                f"❌ **{clan}** wird nicht getrackt. Erst `/clan_track` benutzen!"
            )
        labels = {
            "diamond":    "💎 Diamond Donations",
            "join_leave": "👤 Join / Leave",
            "ranking":    "📊 Ranking Changes",
            "hourly":     "⏰ Stündliche Updates",
        }
        status = "✅ **AN**" if enabled else "❌ **AUS**"
        await interaction.followup.send(
            f"{status} — **{labels[typ]}** für **{clan}** wurde umgeschaltet."
        )

    # ── /notif_status ──────────────────────────────────────────────────────────
    @app_commands.command(name="notif_status",
                          description="⚙️ Zeigt alle Notification-Einstellungen eines Clans")
    @app_commands.describe(clan="Clan Name")
    async def notif_status(self, interaction: discord.Interaction, clan: str):
        await interaction.response.defer()
        clan  = clan.strip().upper()
        entry = db.get_clan_entry(str(interaction.guild_id), clan)
        if entry is None:
            return await interaction.followup.send(f"❌ **{clan}** wird nicht getrackt.")
        notifs = entry.get("notifs", {})
        emb    = embeds.notif_overview(clan, notifs)
        await interaction.followup.send(embed=emb)


async def setup(bot):
    await bot.add_cog(TrackingCog(bot))
