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

intents = discord.Intents.default()
intents.message_content = True


class CWBot(commands.Bot):
    def __init__(self):
        super().__init__(command_prefix=PREFIX, intents=intents, help_command=None)
        self.monitor = Monitor(self)

    async def setup_hook(self):
        await self.load_extension("cogs.clan")
        await self.load_extension("cogs.tracking")
        await self.load_extension("cogs.economy")

        synced = await self.tree.sync()
        print(f"✅ {len(synced)} Slash-Commands registriert")

        await db.gist_restore()
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


@bot.command(name="help")
async def help_cmd(ctx):
    e = discord.Embed(title="🐾 PS99 ClanWar Bot – Commands", color=0x5865F2)
    e.add_field(name="📋 Prefix", value="`!cb <clan>` – Clan Board (Image)", inline=False)
    e.add_field(name="📡 Set Channels", value=(
        "`/set clanrank` `/set diamonds`\n"
        "`/set hourlystats` `/set joinleave`"
    ), inline=False)
    e.add_field(name="🔕 Disable", value=(
        "`/disable clanrank` `/disable diamonds`\n"
        "`/disable hourlystats` `/disable joinleave`"
    ), inline=False)
    e.add_field(name="🔍 Search", value=(
        "`/search` `/history` `/dailystars`\n"
        "`/oldcw` `/exist`"
    ), inline=False)
    e.add_field(name="💰 Economy", value="`/rap` `/cheap`", inline=False)
    e.add_field(name="🔐 Misc", value="`/checkperms` `/help`", inline=False)
    e.set_footer(text="PS99 ClanWar Bot  •  Pull → Save → Compare")
    await ctx.send(embed=e)


if __name__ == "__main__":
    if not DISCORD_TOKEN:
        print("❌ DISCORD_TOKEN fehlt in der .env Datei!")
        exit(1)
    keep_alive()
    bot.run(DISCORD_TOKEN)
