"""
cogs/diamonds.py
/gem_donate  – Donation eintragen + schönes Embed wie Screenshot 2
/gem_lb      – Leaderboard
/gem_total   – Gesamt
"""
import discord
from discord.ext import commands
from discord import app_commands
import aiohttp
import api as ps99
import db, embeds
from fmt import fmt

class DiamondsCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="gem_donate",
                          description="💎 Trägt eine Diamond-Donation ein")
    @app_commands.describe(
        clan        = "Clan Name (z.B. ZYXE)",
        roblox_user = "Roblox Username des Spenders",
        amount      = "Anzahl der gespendeten Diamonds"
    )
    async def gem_donate(self, interaction: discord.Interaction,
                         clan: str, roblox_user: str, amount: float):
        await interaction.response.defer()
        clan   = clan.strip().upper()
        amount = int(amount)
        if amount <= 0:
            return await interaction.followup.send("❌ Anzahl muss > 0 sein!")

        # Clan Diamonds von API holen
        async with aiohttp.ClientSession() as s:
            data = await ps99.get_clan(s, clan)
        clan_diamonds = ps99.deposited_diamonds(data) if data else 0

        db.add_donation(clan, roblox_user, amount, str(interaction.user.id))

        # User-Total nach dem Update
        user_total = sum(
            d["amount"] for d in db.get_donations(clan)
            if d["roblox_user"].lower() == roblox_user.lower()
        )

        # Embed genau wie Screenshot 2
        emb = embeds.diamond_update(clan, roblox_user, amount, user_total, clan_diamonds)
        await interaction.followup.send(embed=emb)

    @app_commands.command(name="gem_lb",
                          description="💎 Diamond Donation Leaderboard eines Clans")
    @app_commands.describe(clan="Clan Name")
    async def gem_lb(self, interaction: discord.Interaction, clan: str):
        await interaction.response.defer()
        clan = clan.strip().upper()
        donations = db.get_donations(clan)
        emb = embeds.diamond_lb(clan, donations)
        await interaction.followup.send(embed=emb)

    @app_commands.command(name="gem_total",
                          description="💎 Gesamt-Diamonds eines Clans")
    @app_commands.describe(clan="Clan Name")
    async def gem_total(self, interaction: discord.Interaction, clan: str):
        await interaction.response.defer()
        clan  = clan.strip().upper()
        total = db.clan_diamond_total(clan)
        donations = db.get_donations(clan)

        e = discord.Embed(title=f"💎 Clan Diamonds  •  {clan}", color=0xE91E8C)
        e.add_field(name="💰 Gesamt",  value=f"**{fmt(total)}**",     inline=True)
        e.add_field(name="👥 Spender", value=f"**{len(donations)}**", inline=True)
        e.timestamp = discord.utils.utcnow()
        await interaction.followup.send(embed=e)

async def setup(bot):
    await bot.add_cog(DiamondsCog(bot))
