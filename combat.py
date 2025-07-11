from dis import disco

from CombatView import CombatView
import quiz_questions

from skills import skills
import discord
from enemies import generate_enemy_wave
import pickledb
import random
import asyncio
from status_effects import (
    apply_status_effects,
    check_dodge,
    apply_healing,
    apply_status_effect,
    apply_buff,
    process_buffs,
    get_effective_stat
)

from db import db

def calculate_skill_effect(user_stats, skill, user_id=None):
    power = skill.get("power", 1.0)
    skill_stat = skill.get("stat") # check if their stats are buffed for Strength or Magic
    equipped_weapon = db.dget(user_id, "equipped_weapon")
    weapon_dmg = equipped_weapon["data"].get("Damage")
    total_dmg = get_effective_stat(user_id, skill_stat) + weapon_dmg
    print(f"[WEAPON DMG]: {weapon_dmg}")
    print(f"[TOTAL DMG]: {total_dmg}")

    if skill["type"] in ["physical", "magic"]:
        amount = int(total_dmg * power)
    else:
        amount = 0

    return int(amount)

class CombatTurnManager:
    def __init__(self, session):
        self.session = session
        self.party = session.members
        self.enemies = session.enemies

        self.turn_order = self.party + list(range(len(self.enemies)))
        self.turn_index = 0
        self.phase = "players"
        self.round_number = 1

    def get_current_actor(self):
        # Just return the current actor by index, no skipping here
        return self.turn_order[self.turn_index]

    def reset_for_next_wave(self):
        self.enemies = self.session.enemies
        self.turn_order = self.party + list(range(len(self.enemies)))
        self.turn_index = 0
        self.round_number = 1

    def advance_turn(self):
        loop_count = 0
        while True:
            self.turn_index = (self.turn_index + 1) % len(self.turn_order)

            actor = self.get_current_actor()
            if self.is_actor_alive(actor):
                break

            loop_count += 1
            if loop_count > len(self.turn_order):
                # Everyone is dead or no valid actor found, break to prevent infinite loop
                break

        self.phase = "players" if self.turn_index < len(self.party) else "enemies"

    def is_actor_alive(self, actor):
        if actor in self.party:
            user_id = str(actor)
            stats = db.dget(user_id, "stats") or {}
            return stats.get("Health", 0) > 0
        else:
            enemy_index = actor
            return self.enemies[enemy_index]["hp"] > 0

    def handle_round_start(self):
        for enemy in self.enemies:
            self.process_effects(enemy)

    def has_mana(self, actor):
        if actor in self.party:
            user_id = str(actor)
            stat = db.dget(user_id, "stats") or {}
            if stat.get("Mana") == 0:
                return False
            return True

    def process_effects(self, entity):
        for debuff in entity.get("debuffs", [])[:]:
            if debuff["name"] in ("burn", "poison"):
                entity["hp"] -= debuff["value"]
            debuff["duration"] -= 1
            if debuff["duration"] <= 0:
                entity["debuffs"].remove(debuff)

    def is_combat_over(self):
        if all(enemy["hp"] <= 0 for enemy in self.enemies):
            return True  # Victory

        if all(db.dget(str(player), "stats").get("Health", 0) <= 0 for player in self.party):
            return True  # Defeat

        return False

def get_user_stats(user_id):
    try:
        stats = db.dget(user_id, "stats")
        return stats if stats is not None else {}
    except KeyError:
        # Key or subkey doesn't exist yet
        return {}

def create_hp_bar(current_hp, max_hp, length=10):
    percentage = current_hp / max_hp
    filled = int(percentage * length)
    empty = length - filled
    bar = f"{'<:hpfull:1389208660906868890>' * filled}{'<:hpmissing:1389208658071781518>' * empty}"
    return f"{bar} {current_hp}/{max_hp} HP"

def green_bar(current_hp, max_hp, length=10):
    percentage = current_hp / max_hp
    filled = int(percentage * length)
    empty = length - filled
    bar = f"{'<:hp1:1389485623793942621>' * filled}{'<:hpmissing:1389208658071781518>' * empty}"
    return f"{bar} {current_hp}/{max_hp} HP"

def blue_bar(current_hp, max_hp, length=10):
    if max_hp == 0 or None:
        return ""
    percentage = current_hp / max_hp
    filled = int(percentage * length)
    empty = length - filled
    bar = f"{'<:mana1:1392789954278588447>' * filled}{'<:hpmissing:1389208658071781518>' * empty}"

    return f"{bar} {current_hp}/{max_hp}MP"


def update_user_hp(user_id, hp_change):
    """
    hp_change: positive for healing, negative for damage
    """
    stats = db.dget(user_id, "stats") or {}
    current_hp = stats.get("CurrentHP", 0)
    max_hp = stats.get("Health", 0)

    new_hp = max(0, min(current_hp + hp_change, max_hp))  # clamp between 0 and max_hp
    stats["CurrentHP"] = new_hp

    db.dadd(user_id, ("stats", stats))
    return new_hp

async def start_turn(channel: discord.TextChannel, turn_manager: CombatTurnManager):
    actor = turn_manager.get_current_actor()

    print(f"[DEBUG] Next turn belongs to: {'Player' if actor in turn_manager.party else 'Enemy'} ({actor})")

    # 🧑 PLAYER TURN
    if actor in turn_manager.party:
        stats = db.dget(str(actor), "stats") or {}

        if stats.get("Health", 0) <= 0:
            await channel.send(f"☠️ <@{actor}> is defeated and cannot act.")
            await asyncio.sleep(1.5)
            turn_manager.advance_turn()
            await start_turn(channel, turn_manager)
            return


        # Check if player is stunned
        if any(debuff["name"] == "stun" for debuff in stats.get("debuffs", [])):
            await channel.send(f"💫 <@{actor}> is stunned and skips their turn!")
            # Process status effects (reduce durations)
            await apply_player_status_effects(actor, channel)
            turn_manager.advance_turn()
            await asyncio.sleep(1.2)
            await start_turn(channel, turn_manager)
            return

        await apply_player_status_effects(actor, channel)

        if turn_manager.is_combat_over():
            session = turn_manager.session
            session.stage += 1
            if session.stage < session.max_waves:
                await channel.send(f"✅ Wave {session.stage} cleared! Get ready for the next one...")
                await asyncio.sleep(5)
                session.enemies = generate_enemy_wave(len(session.members))
                turn_manager.reset_for_next_wave()
                await start_turn(channel, turn_manager)
            else:
                await turn_manager.session.give_rewards()
                await turn_manager.session.end_dungeon("🎉 The party has defeated all waves!")
            return

        enemy_embed = discord.Embed(
            title="⚔️ Enemies",
            description="Here are your enemies:",
            color=discord.Color.dark_red()
        )

        enemy_display = ""
        for enemy in turn_manager.enemies:
            name = enemy["name"]
            hp = enemy.get("hp", 0)
            max_hp = enemy.get("base_hp", 100)

            if hp <= 0:
                bar = f"☠️ {name} is defeated."
            else:
                bar = f"{name}\n{create_hp_bar(hp, max_hp, length=10)}"
            enemy_display += f"{bar}\n\n"

        # Ensure value doesn't exceed 1024 chars
        if len(enemy_display) > 1024:
            enemy_display = enemy_display[:1000] + "\n... (truncated)"

        enemy_embed.add_field(name="Enemies", value=enemy_display, inline=False)

        await channel.send(embed=enemy_embed)
        await asyncio.sleep(1.5)

        # Get player info
        user_id = str(actor)
        user_class = db.dget(user_id, "class")
        player_skills = skills[user_class]
        member = channel.guild.get_member(actor)
        username = member.display_name if member else f"User {actor}"

        view = CombatView(session=turn_manager.session, player_id=actor, player_skills=player_skills)
        user_stats = db.dget(user_id, "stats")
        user_max_hp = user_stats.get("MaxHealth") or 0
        user_max_mana = user_stats.get("MaxMana") or 0
        user_current_hp = user_stats.get("Health") or 0
        user_current_mana = user_stats.get("Mana") or 0
        hp_bar = create_hp_bar(user_current_hp, user_max_hp)
        mana_bar = blue_bar(user_max_mana, user_current_mana)
        embed = discord.Embed(
            title=f"🎯 {username}'s Turn",
            description="Choose your action below.",
            color=discord.Color.gold()
        )
        user_embed = discord.Embed(
            title=f"{username}'s current stats.",
            description = f"{hp_bar} \n{mana_bar}",
        )

        await channel.send(embed=user_embed)
        await channel.send(embed=embed, view=view)
        await view.wait()

        # Process buffs at end of turn (reduce duration)
        process_buffs(user_id)

        turn_manager.advance_turn()
        await asyncio.sleep(1.2)
        await start_turn(channel, turn_manager)

    # ENEMY TURN
    else:
        enemy_index = actor
        enemy = turn_manager.enemies[enemy_index]

        if enemy["hp"] <= 0:
            await channel.send(f"☠️ **{enemy['name']}** is defeated and cannot act.")
            await asyncio.sleep(1.2)
            turn_manager.advance_turn()
            await start_turn(channel, turn_manager)
            return

        # Check if enemy is stunned
        if any(debuff["name"] == "stun" for debuff in enemy.get("debuffs", [])):
            await channel.send(f"💫 **{enemy['name']}** is stunned and skips their turn!")
            # Apply status effects to enemy
            await apply_status_effects(enemy, channel)
            turn_manager.advance_turn()
            await asyncio.sleep(1.2)
            await start_turn(channel, turn_manager)
            return

        await apply_status_effects(enemy, channel)

        # Check if enemy died from status effects
        if enemy["hp"] <= 0:
            await channel.send(f"☠️ **{enemy['name']}** was defeated by status effects!")
            await asyncio.sleep(1.2)
            turn_manager.advance_turn()
            await start_turn(channel, turn_manager)
            return

        await asyncio.sleep(1.5)  # Delay to simulate enemy thinking

        # choose a random member
        import random
        alive_targets = [
            pid for pid in turn_manager.party
            if db.dget(str(pid), "stats").get("Health", 0) > 0
        ]

        if not alive_targets:
            await turn_manager.session.end_dungeon("☠️ The party was wiped out!")
            return

        target_id = random.choice(alive_targets)
        user_id_str = str(target_id)
        member = channel.guild.get_member(target_id)

        stats = db.dget(user_id_str, "stats") or {}
        user_class = db.dget(user_id_str, "class")
        max_hp = stats.get("MaxHealth", 100)
        current_hp = stats.get("Health", 100)

        agility = stats.get("Agility", 1)
        dodge_chance = min(agility * 0.01, 0.5)

        # Use the centralized dodge check
        if check_dodge(stats):
            embed = discord.Embed(
                title=f"**{enemy['name']}** attacks!",
                description=f"hold on, somethings wrong!",
                color=discord.Color.red()
            )
            await channel.send(embed=embed)
            await asyncio.sleep(1.5)
            dodge = discord.Embed(
                title=f"**{member.display_name} dodged the attack!**",
                color=discord.Color.green()
            )
            await channel.send(embed=dodge)
            turn_manager.advance_turn()
            await start_turn(channel, turn_manager)
            return

        # Apply damage
        damage = enemy["power"]
        new_hp = max(current_hp - int(damage), 0)
        stats["Health"] = new_hp
        db.dadd(user_id_str, ("stats", stats))

        if new_hp <= 0:
            await channel.send(f"☠️ <@{target_id}> has fallen in battle!")
            await asyncio.sleep(1.2)

        embed = discord.Embed(
            title=f"**{enemy['name']}** attacks!",
            description=f"<@{target_id}> takes **{damage}** damage!",
            color=discord.Color.red()
        )
        hp_bar = green_bar(new_hp, max_hp)
        embed.add_field(name=f"{member.display_name}'s HP", value=hp_bar, inline=False)

        await channel.send(embed=embed)
        await asyncio.sleep(1.5)

        turn_manager.advance_turn()
        await start_turn(channel, turn_manager)


async def apply_player_status_effects(player_id: int, channel: discord.TextChannel):
    """Apply status effects to a player and handle the results"""
    user_id_str = str(player_id)
    stats = db.dget(user_id_str, "stats") or {}

    # Initialize debuffs if not present
    if "debuffs" not in stats:
        stats["debuffs"] = []

    # Create a temporary entity structure for the status effects system
    player_entity = {
        "name": f"<@{player_id}>",
        "hp": stats.get("Health", 100),
        "debuffs": stats.get("debuffs", [])
    }

    # Apply status effects
    updated_entity = await apply_status_effects(player_entity, channel)

    # Update player stats with new HP and debuffs
    stats["Health"] = max(updated_entity["hp"], 0)
    stats["debuffs"] = updated_entity["debuffs"]

    # Save updated stats
    db.dadd(user_id_str, ("stats", stats))

    # Check if player died from status effects
    if stats["Health"] <= 0:
        await channel.send(f"☠️ <@{player_id}> was defeated by status effects!")
        await asyncio.sleep(1.2)

# Helper functions that can be used in your skill system
def apply_damage_with_effects(target_entity, damage, effect_name=None, effect_value=0, effect_duration=2):
    """Apply damage and optionally add a status effect"""
    target_entity["hp"] -= damage

    if effect_name:
        apply_status_effect(target_entity, effect_name, effect_value, effect_duration)

    return target_entity


def heal_player(user_id: str, power: float):
    """Heal a player using the centralized healing system"""
    stats = db.dget(user_id, "stats") or {}
    heal_amount, updated_stats = apply_healing(stats, power)
    db.dadd(user_id, ("stats", updated_stats))
    return heal_amount


def buff_player(user_id: str, stat: str, multiplier: float, duration: int):
    """Apply a buff to a player"""
    apply_buff(user_id, stat, multiplier, duration)


def get_player_effective_stat(user_id: str, stat_name: str) -> int:
    """Get a player's effective stat value including buffs"""
    return get_effective_stat(user_id, stat_name)