import discord
from discord.ext import commands
from discord import app_commands
import json

import sys
import os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from items import weapon, consumables  # Assuming you store weapons/consumables here
from db import db

# Initialize the Discord client
intents = discord.Intents.default()
intents.members = True
intents.message_content = True
client = commands.Bot(command_prefix=',', intents=intents)

class AdminCommands(app_commands.Group):

    # async def AutoComplete(self,interaction: discord.Interaction, current: str, List[app_commands.Choice[str]]:
    # choices = []
    # ):

    @app_commands.command(name="gold")
    async def adjust(self, interaction: discord.Interaction, amount: int, user: discord.Member):
        if interaction.user.id != 718445888821002271:
            return

        db.set(f"gold_{str(user.id)}", amount)
        db.dump()

    @app_commands.command(name="debug_inventory")
    async def debug_inventory(self, interaction: discord.Interaction, member: discord.Member):
        db.dump()
        user_id = str(interaction.user.id)
        inv = db.get(f"inventory_{member}")
        await interaction.response.send_message(f"```json\n{json.dumps(inv, indent=2)}```", ephemeral=True)

    @app_commands.command(name="hp")
    async def HP(self, interaction: discord.Interaction, amount: int, user: discord.Member):
        if interaction.user.id != 718445888821002271:
            return

        user_stats = db.dget(str(user.id), "stats")
        hp = user_stats["Health"]
        hp += amount
        db.dadd(str(user.id), user_stats)
        db.dump()

    @app_commands.command(name="mp")
    async def MP(self, interaction: discord.Interaction, amount: int, user: discord.Member):
        if interaction.user.id != 718445888821002271:
            return

        user_stats = db.dget(str(user.id), "stats")
        hp = user_stats["Mana"]
        hp += amount
        db.dadd(str(user.id), user_stats)
        db.dump()

    @app_commands.command(name="give")
    async def give(self, interaction: discord.Interaction, item: str, user: discord.Member):
        if interaction.user.id != 718445888821002271:
            return

        db.dget(str(user.id), f"inventory_{str(user.id)}")
