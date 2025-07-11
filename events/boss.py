import discord
from discord.ext import commands
from discord import app_commands
import json

# Replace these with your actual imports

import sys
import os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from enemies import boss_azaroth
from items import weapon, consumables  # Assuming you store weapons/consumables here
from dungeon_manager import active_dungeon_sessions
from db import db
from events.boss_session import DungeonJoinView, DungeonSession

# Initialize the Discord client
intents = discord.Intents.default()
intents.members = True
intents.message_content = True
client = commands.Bot(command_prefix=',', intents=intents)

class boss(app_commands.Group):

    @app_commands.command(name="start")
    async def start_dungeon(self, interaction: discord.Interaction):
        await interaction.response.defer()
        leader_id = interaction.user.id

        if leader_id in active_dungeon_sessions:
            await interaction.followup.send_message(
                content="You are already in an active dungeon session!",
                ephemeral=True
            )

        # Setup permissions for members
        overwrites = {
            interaction.guild.default_role: discord.PermissionOverwrite(read_messages=False)
        }
        # Create the channel
        channel = await interaction.guild.create_text_channel(
            name=f"dungeon-{interaction.user.name}",
            overwrites=overwrites,
            reason="New Dungeon Party Created"
        )

        # Create session first and include leader as initial member
        session = DungeonSession(leader_id, channel, client)  # channel.id will be set after creation
        session.members = [leader_id]  # ✅ Add leader to members
        active_dungeon_sessions[leader_id] = session
        session.is_boss_fight = True

        for member_id in session.members:
            member = interaction.guild.get_member(member_id)
            if member:
                overwrites[member] = discord.PermissionOverwrite(read_messages=True, send_messages=True)


        session.channel_id = channel.id  # ✅ Save channel ID to session

        # Send recruitment embed in original channel
        embed = discord.Embed(
            title="🛡️ Dungeon Raid Recruitment",
            description=f"Party Leader: <@{leader_id}>\n\n🧍 <@{leader_id}>",
            color=discord.Color.gold()
        )
        view = DungeonJoinView(session, active_dungeon_sessions)
        recruitment_msg = await interaction.followup.send(embed=embed, view=view)
        session.recruitment_message = recruitment_msg

