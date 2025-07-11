from datetime import datetime, timedelta
import time
import discord
import sys
import os
import random
import enum
from mpmath.ctx_mp_python import return_mpc

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from db import db

# Initialize the Discord client
from discord.ext import commands
from discord import app_commands
intents = discord.Intents.default()
intents.members = True
intents.message_content = True
client = commands.Bot(command_prefix=',', intents=intents)

def can_claim_daily(user_id):
    user_id = str(user_id)
    last_claim = db.get(f'daily_{user_id}')

    if not last_claim:
        return True

    current_time = time.time()
    time_difference = current_time - last_claim

    return time_difference >= 86400

def update_daily_claim(user_id):
    user_id = str(user_id)
    db.set(f'daily_{user_id}', time.time())
    db.dump()

def get_time_until_next_daily(user_id):
    user_id = str(user_id)
    last_claim = db.get(f'daily_{user_id}')

    if not last_claim:
        return 0

    current_time = time.time()
    time_passed = current_time - last_claim
    time_remaining = 86400 - time_passed

    return max(0, time_remaining)


@client.tree.command(name="daily")
async def daily(interaction: discord.Interaction):
    user_id = str(interaction.user.id)

    if not can_claim_daily(user_id):
        remaining_seconds = get_time_until_next_daily(user_id)
        hours = int(remaining_seconds // 3600)
        minutes = int((remaining_seconds % 3600) // 60)

        embed = discord.Embed(
            title="🔔Daily reward already claimed!",
            description = f"You can claim your next daily reward in **{hours}h {minutes}m**",
            color = discord.Color.orange()
        )
        await interaction.response.send_message(embed=embed)
        return

    import random
    reward = random.randint(50,200)
    gold = db.get(f"gold_{user_id}")
    db.set(f"gold_{user_id}",gold + reward)

    embed = discord.Embed(
        title="🎁 Daily Reward Claimed!",
        description=f"You received **{reward}** coins!",
        color=discord.Color.green()
    )

    update_daily_claim(user_id)

    await interaction.response.send_message(embed=embed)

class black_red(enum.Enum):
    black = "black"
    red = "red"
@client.tree.command(name="roulette", description="Let's go Gambling!")
async def roulette(interaction: discord.Interaction, choice: black_red, amount: int):
    user_id = str(interaction.user.id)
    gold = db.get(f"gold_{user_id}")
    reward = (amount * 2)
    winning_color = random.choice(["black", "red"])

    # User tries to gamble more than they have
    if amount > gold:
        embed = discord.Embed(
            title="You can't gamble more than the amount you have in your wallet!",
            description = "i think that's common sense, brother.",
            color=discord.Color.red()
        )
        await interaction.response.send_message(embed=embed)
        return

    # User gambles with nothing!?
    if amount == 0:
        embed = discord.Embed(
            title="You can't gamble nothing.",
            description="i think that's common sense, brother.",
            color=discord.Color.red()
        )
        await interaction.response.send_message(embed=embed)
        return_mpc

    # User gambles properly this time,
    if gold >= amount:
        if choice.value == winning_color:
            db.set(f"gold_{user_id}", gold+reward)
            embed = discord.Embed(
                title="Winner Winner Chicken Dinner!",
                description=f"You won **{reward}** Gold! You now have **{gold+reward}** Gold in your wallet! \n I know someone called Rager winning as big as this.",
                color=discord.Color.green()
            )
            await interaction.response.send_message(embed=embed)
            return
        else:
            db.set(f"gold_{user_id}", gold-amount)
            embed = discord.Embed(
                title="99% of gamblers quit before they win big.",
                description=f"You lost {amount} Gold",
                color=discord.Color.red()
            )
            content = "-# No, I didn't make that up. You should definitely gamble more."
            await interaction.response.send_message(embed=embed, content=content)
            return
