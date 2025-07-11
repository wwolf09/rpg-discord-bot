from datetime import datetime, timedelta

import discord
from discord.ext import commands
from dotenv import load_dotenv

from dungeon_manager import active_dungeon_sessions
from dungeon_session import DungeonSession, DungeonJoinView
from skills import skills as all_class_skills

from items import weapon as weapon
import json

load_dotenv()
import quiz_questions
import random
import asyncio

import psutil
import os
from commands.shop_handler import shop
from commands.games import daily, roulette
from commands.admin import AdminCommands

# Initialize the Discord client
intents = discord.Intents.default()
intents.members = True
intents.message_content = True
client = commands.Bot(command_prefix=',', intents=intents)

client.tree.add_command(shop)
client.tree.add_command(daily)
client.tree.add_command(roulette)
client.tree.add_command(AdminCommands(name="admin", description="admin commands for quix"))


DC_TOKEN = os.getenv("TOKEN")
from db import db

def setup_user_class(user_id, chosen_class):
    if chosen_class not in quiz_questions.classes:
        return False

    user_id = str(user_id)

    base_stats = quiz_questions.classes[chosen_class].copy()
    print(base_stats)
    starter_weapon_name = base_stats.pop("Weapon", None)
    print(f"[WEAPON_NAME]: {starter_weapon_name}")

    db.dadd(user_id, ("stats", base_stats))

    inv_key = f"inventory_{user_id}"
    db.dadd(inv_key, ("consumables", None))
    db.dcreate(inv_key)
    db.dump()

    class_weapons = weapon.get(chosen_class.lower() or chosen_class.title())
    print(class_weapons)
    weapon_data = class_weapons.get(str(starter_weapon_name)) if class_weapons else None
    print(f"[WEAPON_DATA]: {weapon_data}")
    if not weapon_data:
        print(f"[ERROR] Weapon Data Not Found")

    weapon_entry = {
        "name": starter_weapon_name,
        "data": weapon_data
    }
    print(weapon_entry)

    db.dadd(inv_key, ("weapon", [weapon_entry]))
    db.dadd(user_id, ("equipped_weapon", weapon_entry))
    db.dump()

    skill_template = all_class_skills.get(chosen_class, {})
    upgradable_skills = {}

    for skill_name in skill_template:
        upgradable_skills[skill_name] = {
        "level": 1,
        "cooldown": 0,
        "max_level": 5,
        "uses": 0,
        "last_used_turn": 0,
        "equipped": True
        }

    db.set(f"skills_{user_id}", upgradable_skills)
    db.dump()

def setup_user(user):
    user_id = str(user)
    if not db.exists(user_id):
        db.dcreate(user_id)
        db.dcreate(f"inventory_{user_id}")
        db.dadd(user_id, ("stats", {}))
        db.set(f"gold_{user_id}", 0)
        db.dadd(user_id, ("equipped_weapon", None))
        db.dadd(user_id, ("xp", 0))
        db.dadd(user_id, ("level", 1))
        db.dadd(user_id, ("awakening", False))
        db.dadd(user_id, ("class", None))
        db.dadd(user_id, ("subclass", None))
        db.dump()

def get_mem():
    process = psutil.Process(os.getpid())
    mem = process.memory_info().rss / 1024 / 1024
    return round(mem, 2)

# Class Assignment
@client.tree.command(name="classpick")
async def class_pick(interaction: discord.Interaction):
    score = {"swordsman": 0, "mage": 0, "rogue": 0, "healer": 0}
    user = interaction.user
    user_id = str(user.id)

    setup_user(user_id)

    def check(m):
        return m.author == user and isinstance(m.channel, discord.DMChannel)

    if interaction.guild is not None:
        await interaction.response.send_message(content="Please proceed to DMS for a private experience! Use the command /classpick in DMs to proceed.", ephemeral=True)
        return

    await interaction.channel.send(content=f"{user.name}, prepare to discover your true calling...")

    for i, q in enumerate(quiz_questions.quiz_questions, 1):
        question_text = f"**Q{i}: {q['question']}**\n"
        for option, data in q['choices'].items():
            question_text += f"{option}. {data['text']}\n"
        await interaction.channel.send("<a:save3d:1385556752489119825> Saving...")
        # await asyncio.sleep(2)
        await interaction.channel.send(question_text)

        try:
            msg = await client.wait_for("message", timeout=60.0, check=check)
        except asyncio.TimeoutError:
            await interaction.channel.send("⏰ User took too long to respond. Quiz cancelled")
            return

        answer = msg.content.upper().strip()

        if answer not in q['choices']:
            await interaction.channel.send("❌ Invalid choice. Please answer A, B, C, or D.")
            return

        for class_name, pts in q["choices"][answer].items():
            if class_name in score:
                score[class_name] += pts

    max_score = max(score.values())
    tied = [cls for cls, pts in score.items() if pts == max_score]

    # pick one at random
    chosen_class = random.choice(tied)

    db.dadd(str(user.id), ("class", chosen_class))
    db.dump()

    await interaction.channel.send(f"Destiny awaits adventurer.")
    await asyncio.sleep(2)
    await interaction.channel.send(f"The calling has arrived.")
    await asyncio.sleep(1)
    await interaction.channel.send("<a:save3d:1385556752489119825> Saving...")
    await interaction.channel.send(f"🎉 You are a **{chosen_class.capitalize()}**! Destiny awaits, {user.global_name}.")

    options = quiz_questions.subclasses[chosen_class]
    setup_user_class(user_id, chosen_class)

    await interaction.channel.send(f"Unlockable Classes upon Awakening:\n" + "\n".join(
        f"{chr(65 + i)}. {sub}" for i, sub in enumerate(options)
    ))

@client.event
async def on_ready():
    await client.tree.sync()
    print('Bot is ready.')

def xp_for_next_level(level):
    return 5 * (level ** 2) + 50

cooldowns = {}
@client.event
async def on_message(message: discord.Message):
    if message.author.bot:
        return
    user_id = str(message.author.id)
    setup_user(user_id)
    now = datetime.now()
    cooldowns[user_id] = now + timedelta(seconds=60)

    user_data = db.get(user_id)
    user_xp = db.dget(user_id, "xp")
    xp_gain = random.randint(5,10)
    total_xp = user_xp + xp_gain

    db.dadd(user_id, ("xp", int(total_xp)))
    user_data["xp"] += xp_gain

    level_up = False
    while user_data["xp"] >= xp_for_next_level(user_data["level"]):
        user_data["xp"] -= xp_for_next_level(user_data["level"])
        level_up = True
        db.dadd(user_id, ("level", user_data["level"] + 1))

    await client.process_commands(message)

@client.tree.command(name="awaken")
async def awaken(interaction: discord.Interaction):
    if interaction.guild is not None:
        await interaction.response.send_message(content="Please proceed to DMS for a private experience! Use the command /classpick in DMs to proceed.", ephemeral=True)
        return

    user_id = str(interaction.user.id)
    setup_user(user_id)

    awaken = db.dget(user_id, "awakening")
    print(awaken)

    if db.dget(user_id, "class") is None:
        await interaction.channel.send("You don't have a class yet! Use the command /classpick to determine your class.")
        return
    if awaken is False:
        await interaction.channel.send("You are not yet eligible for Awakening! Reach level 10 first to awaken")
        return

    main_class = db.dget(user_id, "class")
    print(main_class)
    available = quiz_questions.subclasses.get(main_class)
    print(available)

    if not available:
        await interaction.channel.send("⚠️ Something went wrong: There are no subclasses for your class!")
        return

    ## choices
    letters = ["A", "B", "C", "D"]
    options = {letter: subclass for letter, subclass in zip(letters, available)}
    prompt = f"🎉 Choose your **subclass** for `{main_class.capitalize()}`:\n" + "\n".join(f"{letter}) {sub}" for letter, sub in options.items())
    await interaction.channel.send(prompt)

    def check(m):
        return m.author == interaction.user and m.channel == interaction.channel

    try:
        msg = await client.wait_for("message", timeout=60.0, check=check)
    except asyncio.TimeoutError:
        await interaction.channel.send("Took too long! Try the command again.")

    choice = msg.content.upper().strip()

    if choice not in options:
        await interaction.channel.send("❌ Invalid Option! Please choose A, B, C, or D next time!")
        return

    chosen_subclass = options[choice]
    db.dadd(user_id, ("subclass", chosen_subclass))

    await interaction.channel.send(content=f"Congrats {chosen_subclass} for awakening. ")

    print(chosen_subclass)

# @client.tree.command(name="quest")
# async def quest(interaction: discord.Interaction):

class InventorySelect(discord.ui.Select):
    def __init__(self, user_id):
        self.user_id = user_id

        options = []

        weapon_list = db.get(f"weapon_{user_id}") or []
        potion_list = db.dgetall(f"inventory_{user_id}") or []

        self.weapon_items = weapon_list
        self.potion_items = potion_list

        if weapon_list:
            options.append(discord.SelectOption(label=f"Weapons ({len(weapon_list)})", value="weapons"))
        if potion_list:
            options.append(discord.SelectOption(label=f"Consumables ({len(weapon_list)})", value="potions"))

        self().__init__(placeholder="Select Category", options = options)

    async def callback(self, interaction: discord.Interaction):
        embed = discord.Embed(color=discord.Color.green())
        if self.values[0] == "weapons":
            weapons = self.weapon_items
            equipped = db.dget(self.user_id, "equipped_weapon") or "None"
            embed.title = "⚔️ Weapons"
            embed.description = "\n".join(
                [f'{'🔹' if item != equipped else '✅[Equipped]'} {item}' for item in weapons]
            )
            embed.set_footer(text=f"Equipped: {equipped}")
        elif self.values[0] == "potions:":
            potions = self.potion_items
            embed.title = "🧪 Potions"
            embed.description = "\n".join([f"🔹 {item}" for item in potions])
        await interaction.response.edit_message(embed=embed, view=self.view)

class InventoryView(discord.ui.View):
    def __init__(self, user_id):
        super().__init__()
        self.add_item(InventorySelect(user_id))

@client.tree.command(name="inventory")
async def inventory(interaction: discord.Interaction):
    user_id = str(interaction.user.id)

    weapons = db.dget(f"inventory_{user_id}", "weapon") or []
    # potions = db.dget(f"inventory{user_id}") or []
    equipped = db.dget(user_id, "equipped_weapon") or "None"
    print(weapons)

    if len(weapons) <=5:
        embed = discord.Embed(title=f"{interaction.user.name}'s Inventory", color=discord.Color.blue())
        if weapons:
            embed.add_field(
                name="⚔️ Weapons",
                value = "\n".join(
                    [f"{'🔹' if item != equipped else '✅[Equipped]'} {item}" for item in weapons]
                ),
                inline=False,
            )
        embed.set_footer(text=f"Equipped Weapon")
        await interaction.channel.send(embed=embed)

@client.tree.command(name="equip")
async def equip(interaction: discord.Interaction, item_name: str):
    user_id = str(interaction.user.id)

    if not db.exists(user_id):
        setup_user(user_id)

    user_class = db.dget(user_id, "class")
    category = "weapon"
    inventory = db.dget(f"inventory_{user_id}", category)
    item_data = weapon.get(user_class, {}).get(item_name)

    if not item_data:
        await interaction.response.send_message(content = "that item doesn't exist or not available for your class.", ephemeral = True)
        return

    db.dadd(user_id, ("equipped_weapon", item_name))

    embed = discord.Embed(title = "✅ Equipped!", color = discord.Color.green())
    embed.add_field(name="Weapon", value = f"**{item_name}**", inline=False)
    embed.add_field(name="Damage", value = item_data.get("Damage", "N/A"), inline=False)
    embed.add_field(name="Effect", value= item_data.get("Effect") or "None", inline=False)
    embed.set_footer(text="Good luck out there adventurer!")

    await interaction.channel.send(embed=embed)

# @client.tree.command(name="dungeon")
# async def dungeon(interaction: discord.Interaction):

def create_hp_bar(current_hp, max_hp, length=10):
    percentage = current_hp / max_hp
    filled = int(percentage * length)
    empty = length - filled
    bar = f"{'<:hpfull:1389208660906868890>' * filled}{'<:hpmissing:1389208658071781518>' * empty}"
    return f"{bar}"

@client.tree.command(name="stats")
async def stats(interaction: discord.Interaction):
    user_id = str(interaction.user.id)

    user_class = db.dget(user_id, "class")
    sub_class = db.dget(user_id, "subclass") or "None"
    level = db.dget(user_id, "level")
    xp = db.dget(user_id, "xp")
    gold = db.get(f"gold_{user_id}")
    stats_dict = db.dget(user_id, "stats") or "None"
    equipped_weapon = db.dget(user_id, "equipped_weapon") or "None"

    health = stats_dict.get("Health")
    maxhp = stats_dict.get("MaxHealth")

    next_xp = xp_for_next_level(level)
    xp_bar = create_hp_bar(xp, next_xp)

    hp_bar = create_hp_bar(health, maxhp)

    weapon_data = weapon.get(user_class.lower(), {}).get(equipped_weapon, {})
    effect = weapon_data.get("Effect", "None")

    stat_lines = []

    stats_to_show = [
        ("Strength", "Strength"),
        ("Magic Damage", "MagicDmg"),
        ("Mana Capacity", "Mana"),
        ("Critical Chance", "CritChance"),
        ("Agility", "Agility")
    ]

    stat_lines = []
    for display_name, key in stats_to_show:
        stat_lines.append(f"**{display_name}**: {stats_dict.get(key, 0)}")

    #embed
    embed = discord.Embed(title = f"📜{interaction.user.name}'s Character Sheet", color=discord.Color.dark_gold())
    embed.add_field(name="Health", value=f"{health}/{maxhp}\n {hp_bar} \n", inline=True)
    embed.add_field(name="Class", value=f"{str(user_class).capitalize()} ({sub_class})", inline=True)
    embed.add_field(name="Level", value=f"{level}", inline=True)
    print(xp)
    embed.add_field(name="XP", value=f"{xp} / {next_xp}\n{xp_bar}", inline= True)
    embed.add_field(name="Gold", value = f"{gold}", inline = True)
    embed.add_field(name="Weapon", value=equipped_weapon, inline = True)
    embed.add_field(name="Stats", value="\n".join(stat_lines), inline=False)

    await interaction.channel.send(embed = embed)


@client.tree.command(name="start_dungeon")
async def start_dungeon(interaction: discord.Interaction):
    await interaction.response.defer()
    leader_id = interaction.user.id

    if leader_id in active_dungeon_sessions:
        await interaction.response.send_message(
            content="You are already in an active dungeon session!",
            ephemeral=True
        )
        return

    # Create session first and include leader as initial member
    session = DungeonSession(leader_id, None, client)  # channel.id will be set after creation
    session.members = [leader_id]  # ✅ Add leader to members
    active_dungeon_sessions[leader_id] = session

    # Setup permissions for members
    overwrites = {
        interaction.guild.default_role: discord.PermissionOverwrite(read_messages=False)
    }

    for member_id in session.members:
        member = interaction.guild.get_member(member_id)
        if member:
            overwrites[member] = discord.PermissionOverwrite(read_messages=True, send_messages=True)

    # Create the channel
    channel = await interaction.guild.create_text_channel(
        name=f"dungeon-{interaction.user.name}",
        overwrites=overwrites,
        reason="New Dungeon Party Created"
    )
    session.channel_id = channel.id  # ✅ Save channel ID to session

    # Send recruitment embed in original channel
    embed = discord.Embed(
        title="🛡️ Dungeon Raid Recruitment",
        description=f"Party Leader: <@{leader_id}>\n\n🧍 <@{leader_id}>",
        color=discord.Color.gold()
    )
    view = DungeonJoinView(session, active_dungeon_sessions)
    recruitment_msg = await interaction.channel.send(embed=embed, view=view)
    session.recruitment_message = recruitment_msg

@client.tree.command(name="ping")
async def ping(interaction: discord.Interaction):
    latency_ms = round(client.latency * 1000)
    await interaction.channel.send(f'pong! {latency_ms}ms!')
    mem = get_mem()
    await interaction.channel.send(f"current memory: {mem} MB")


client.run(DC_TOKEN)
