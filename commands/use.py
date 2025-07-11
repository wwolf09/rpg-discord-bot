import discord
from discord.ext import commands
from discord import app_commands

# Replace these with your actual imports
import pickledb
import sys
import os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from items import weapon, consumables  # Assuming you store weapons/consumables here

# Initialize the Discord client
intents = discord.Intents.default()
intents.members = True
intents.message_content = True
client = commands.Bot(command_prefix=',', intents=intents)
db = pickledb.load('data', auto_dump=True)


@client.tree.command(name="use")
async def