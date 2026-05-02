"""
main.py  –  PS99 ClanWar Bot
Starte mit:  python main.py
"""

import asyncio
import discord
from discord.ext import commands

from config import DISCORD_TOKEN, PREFIX, RENDER_URL
from monitor import Monitor
from keepalive import keep_alive
import db

# ── Bot-Setup ─────────────────────────────────────────────────────────────────
intents = discord.Intents.default()
intents.message_content = True

class CWBot(commands.Bot):
    def __init__(self):
        super().__init__(command_prefix=PREFIX, intents=intents, help_command=None)
        self.monitor = Monitor(self)

    async def setup_hook(self):
        # Cogs laden
        await self.load_extension("cogs.clan")
        await self.load_extension("cogs.tracking")
        await self.load_extension("cogs.diamonds")

        # Slash-Commands global registrieren
        synced = await self.tree.sync()
        print(f"✅ {len(synced)} Slash-Commands registriert")

        # Gist-Backup wiederherstellen (falls vorhanden)
        await db.gist_restore()

        # Monitor starten
        self.monitor.start()

    async def on_ready(self):
        print(f"✅ Bot online als {self.user}  (ID: {self.user.id})")
        await self.change_presence(
            activity=discord.Activity(
                type=discord.ActivityType.watching,
                name="PS99 Clan Wars 🐾"
            )
        )

    async def on_command_error(self, ctx, error):
        if isinstance(error, commands.CommandNotFound):
            return
        print(f"❌ Command Error: {error}")


bot = CWBot()

# ── !help override ─────────────────────────────────────────────────────────────
@bot.command(name="help")
async def help_cmd(ctx):
    e = discord.Embed(
        title="🐾 PS99 ClanWar Bot – Commands",
        color=0x5865F2
    )
    e.add_field(name="📋 Prefix Commands", value=(
        "`!cb <clan>` – Großes Clan-Dashboard\n"
    ), inline=False)
    e.add_field(name="🏆 Clan", value=(
        "`/clan` `/clan_rank` `/clan_stats`\n"
        "`/top_clans` `/contributors` `/member_stats`"
    ), inline=False)
    e.add_field(name="📡 Tracking", value=(
        "`/clan_track` `/clan_untrack` `/clan_list`"
    ), inline=False)
    e.add_field(name="🔔 Notifications", value=(
        "`/notif_toggle` `/notif_status`"
    ), inline=False)
    e.add_field(name="💎 Diamonds", value=(
        "`/gem_donate` `/gem_lb` `/gem_total`"
    ), inline=False)
    e.set_footer(text="PS99 ClanWar Bot  •  Pull → Save → Compare")
    await ctx.send(embed=e)


if __name__ == "__main__":
    if not DISCORD_TOKEN:
        print("❌ DISCORD_TOKEN fehlt in der .env Datei!")
        exit(1)

    # Keep-alive für Render starten (läuft im Hintergrund-Thread)
    keep_alive()

    # Bot starten
    bot.run(DISCORD_TOKEN)
