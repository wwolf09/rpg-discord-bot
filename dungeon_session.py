# dungeon_session.py
import asyncio
from dis import disco

import discord
from openpyxl.styles.builtins import total

from CombatView import CombatView
from combat import CombatTurnManager, start_turn
from dungeon_manager import active_dungeon_sessions
from enemies import generate_enemy_wave
from skills import skills
import random
from enemies import calculate_scaled_rewards
from db import db

def xp_for_next_level(level):
    return 5 * (level ** 2) + 50

def handle_xp_gain(user_data, xp_gained):
    user_xp = db.dget(user_data, "xp")
    leveled_up = False

    level = db.dget(user_data, "level")
    user_xp += xp_gained

    while user_xp >= xp_for_next_level(level):
        user_xp -= xp_for_next_level(level)
        level += 1
        leveled_up = True

    db.dadd(user_data, ("xp", user_xp))
    db.dadd(user_data, ("level", level))
    db.dump()

    return leveled_up, level, user_xp


class DungeonSession:
    def __init__(self, leader_id, channel_id, client):
        self.leader_id = leader_id
        self.channel_id = channel_id
        self.members = [leader_id]
        self.in_progress = False
        self.stage = 0
        self.max_waves = 1
        self.started = False
        self.client = client

        self.recruitment_message = None

    def add_member(self, user_id):
        if user_id not in self.members:
            self.members.append(user_id)

    async def end_dungeon(self, reason: str):
        channel = self.client.get_channel(int(self.channel_id))
        if channel is None:
            channel = await self.client.fetch_channel(int(self.channel_id))

        if channel:
            try:
                msg = await channel.send(reason)

                if self.leader_id in active_dungeon_sessions:
                    del active_dungeon_sessions[self.leader_id]

                await asyncio.sleep(5)
                await msg.edit(content=f"Deleting #{channel.name} in  5.")
                await asyncio.sleep(1)
                await msg.edit(content=f"Deleting #{channel.name} in  4.")
                await asyncio.sleep(1)
                await msg.edit(content=f"Deleting #{channel.name} in  3.")
                await asyncio.sleep(1)
                await msg.edit(content=f"Deleting #{channel.name} in  2.")
                await asyncio.sleep(1)
                await msg.edit(content=f"Deleting #{channel.name} in  1.")
                await asyncio.sleep(1)

                await channel.delete()

            except Exception as e:
                print(f"Error in end_dungeon: {e}")
        else:
            print("Channel not found when ending dungeon.")

    async def give_rewards(session):
        total_xp, total_gold = calculate_scaled_rewards(session.enemies)
        party = session.members

        bonus_gold = 0
        if random.random() < 0.1:
            bonus_gold = random.randint(10, 50)
            total_gold += bonus_gold

        for user_id in party:
            user_stats = db.dget(str(user_id), "stats") or {}
            current_xp = db.dget(str(user_id), "xp") or 0

            current_gold = db.get(f"gold_{user_id}") or 0
            new_gold = current_gold + total_gold
            db.set(f"gold_{user_id}", new_gold)
            db.dadd(str(user_id), ("stats", user_stats))
            db.dump()
            handle_xp_gain(str(user_id), total_xp)

            try:
                member = session.client.get_user(user_id)
                if member:
                    msg = f"🎉 You gained {total_xp} XP and {total_gold} Gold from the dungeon!"
                    if bonus_gold > 0:
                        msg += f" (Bonus Gold: {bonus_gold}!)"
                    await member.send(msg)
            except:
                pass

        channel = session.client.get_channel(session.channel_id)
        if channel:
            msg = f"🏆 Dungeon cleared! Each member gained {total_xp} XP and {total_gold} Gold."
            if bonus_gold > 0:
                msg += f" Bonus gold awarded: {bonus_gold}!"
            await channel.send(msg)

class DungeonJoinView(discord.ui.View):
    def __init__(self, session, active_sessions):
        super().__init__(timeout=300)
        self.session = session
        self.active_sessions = active_sessions

    @discord.ui.button(label="Join Dungeon", style=discord.ButtonStyle.green)
    async def join(self, interaction: discord.Interaction, button: discord.ui.Button):
        user = interaction.user

        if user.id in self.session.members:
            await interaction.response.send_message("You already joined!", ephemeral=True)
            return

        self.session.add_member(user.id)

        embed = discord.Embed(
            title="🛡️ Dungeon Raid Recruitment",
            description=f"Party Leader: <@{self.session.leader_id}>\n\n" +
                        "\n".join([f"🧍 <@{uid}>" for uid in self.session.members]),
            color=discord.Color.gold()
        )
        await interaction.message.edit(embed=embed, view=self)
        await interaction.response.send_message(f"{user.mention} joined the dungeon party!", ephemeral=True)

    @discord.ui.button(label="Leave Party", style=discord.ButtonStyle.red)
    async def leave(self, interaction: discord.Interaction, button: discord.ui.Button):
        user = interaction.user
        if user.id not in self.session.members:
            await interaction.response.send_message("You're not in this party.", ephemeral=True)
            return

        if user.id == self.session.leader_id:
            await interaction.response.send_message("Party leader can't leave. Use Cancel instead.", ephemeral=True)
            return

        self.session.members.remove(user.id)

        embed = discord.Embed(
            title="🛡️ Dungeon Raid Recruitment",
            description=f"Party Leader: <@{self.session.leader_id}>\n\n" +
                        "\n".join([f"🧍 <@{uid}>" for uid in self.session.members]),
            color=discord.Color.gold()
        )
        await interaction.message.edit(embed=embed, view=self)
        await interaction.response.send_message("You've left the dungeon party.", ephemeral=True)

    @discord.ui.button(label="Cancel Dungeon", style=discord.ButtonStyle.grey, row=1)
    async def cancel(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.session.leader_id:
            await interaction.response.send_message("Only the party leader can cancel this dungeon.", ephemeral=True)
            return

        # Remove from active sessions using the shared dict
        self.active_sessions.pop(self.session.leader_id, None)

        # Optional: delete channel
        raid_channel = interaction.guild.get_channel(self.session.channel_id)
        if raid_channel:
            await raid_channel.delete(reason="Dungeon cancelled")

        await interaction.message.edit(
            embed=discord.Embed(
                title="❌ Dungeon Cancelled",
                description="The leader has disbanded the party.",
                color=discord.Color.red()
            ),
            view=None
        )
        await interaction.response.send_message("Dungeon cancelled.", ephemeral=True)

    @discord.ui.button(label="Start Dungeon", style=discord.ButtonStyle.success)
    async def start(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.session.leader_id:
            await interaction.response.send_message("Only the party leader can start the dungeon.", ephemeral=True)
            return

        dungeon_channel = interaction.guild.get_channel(self.session.channel_id)
        for member_id in self.session.members:
            member = interaction.guild.get_member(member_id)
            if member:
                await dungeon_channel.set_permissions(
                    member,
                    read_messages=True,
                    send_messages=True
                )

        if self.session.recruitment_message:
            try:
                await self.session.recruitment_message.edit(view=None)
            except discord.NotFound:
                pass

        # Spawn enemies
        self.session.enemies = generate_enemy_wave(len(self.session.members))

        # Store and start the combat turn manager
        turn_manager = CombatTurnManager(self.session)

        # Start turn loop
        await dungeon_channel.send(f"🧩 Dungeon started by <@{self.session.leader_id}>!")
        await start_turn(dungeon_channel, turn_manager)


