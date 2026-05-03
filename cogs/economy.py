"""
cogs/economy.py
/rap   – RAP Informations for a PS99 item
/cheap – Get information about cheap Huge pets
"""

import discord
from discord.ext import commands
from discord import app_commands
import aiohttp

import api as ps99
from fmt import fmt


def _item_name(item: dict) -> str:
    cd = item.get("configData", {})
    return cd.get("id", "Unknown")

def _item_value(item: dict) -> int:
    return item.get("value", 0)

def _is_huge(item: dict) -> bool:
    cd = item.get("configData", {})
    return str(cd.get("pt", "")).lower() == "huge" or "huge" in str(cd.get("id", "")).lower()


class EconomyCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    # ── /rap ──────────────────────────────────────────────────────────────────
    @app_commands.command(name="rap", description="💰 RAP Informations for a PS99 item")
    @app_commands.describe(item="Item name or ID (e.g. HugeDog, TitanCorgi)")
    async def rap(self, interaction: discord.Interaction, item: str):
        await interaction.response.defer()
        try:
            async with aiohttp.ClientSession() as s:
                data = await ps99.get_rap(s)
            if not data:
                return await interaction.followup.send("❌ RAP API not available right now.")

            query = item.strip().lower()
            matches = [
                x for x in data
                if query in _item_name(x).lower()
            ]

            if not matches:
                return await interaction.followup.send(
                    f"❌ No item found matching **{item}**."
                )

            # Exact match first, otherwise take closest
            exact = next((x for x in matches if _item_name(x).lower() == query), None)
            results = [exact] if exact else matches[:5]

            e = discord.Embed(
                title=f"💰 RAP  •  {item}",
                color=0xFFD700,
            )
            for x in results:
                name = _item_name(x)
                val  = _item_value(x)
                e.add_field(name=name, value=f"💰 **{fmt(val)}**", inline=True)

            e.set_footer(text="Recent Average Price  •  ps99.biggamesapi.io")
            e.timestamp = discord.utils.utcnow()
            await interaction.followup.send(embed=e)
        except Exception as ex:
            await interaction.followup.send(f"❌ Error: {ex}")

    # ── /cheap ────────────────────────────────────────────────────────────────
    @app_commands.command(name="cheap", description="🐾 Get information about cheap Huge pets")
    async def cheap(self, interaction: discord.Interaction):
        await interaction.response.defer()
        try:
            async with aiohttp.ClientSession() as s:
                data = await ps99.get_rap(s)
            if not data:
                return await interaction.followup.send("❌ RAP API not available right now.")

            # Filter Huge pets and sort by price ascending
            huges = [x for x in data if _is_huge(x) and _item_value(x) > 0]
            if not huges:
                return await interaction.followup.send("❌ No Huge pet data found.")

            huges.sort(key=_item_value)
            top = huges[:10]

            lines = []
            for i, x in enumerate(top, 1):
                name = _item_name(x)
                val  = _item_value(x)
                lines.append(f"**{i}.** `{name}` — 💰 **{fmt(val)}**")

            e = discord.Embed(
                title="🐾 Cheapest Huge Pets  •  PS99",
                description="\n".join(lines),
                color=0x5865F2,
            )
            e.set_footer(text="Sorted by RAP (lowest first)  •  ps99.biggamesapi.io")
            e.timestamp = discord.utils.utcnow()
            await interaction.followup.send(embed=e)
        except Exception as ex:
            await interaction.followup.send(f"❌ Error: {ex}")


async def setup(bot):
    await bot.add_cog(EconomyCog(bot))
