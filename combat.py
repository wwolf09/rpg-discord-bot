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
    skill_stat = skill.get("stat")
    equipped_weapon = db.dget(user_id, "equipped_weapon")
    weapon_dmg = equipped_weapon["data"].get("Damage", 0)
    total_dmg = get_effective_stat(user_id, skill_stat) + weapon_dmg

    if skill["type"] in ["physical", "magic"]:
        amount = int(total_dmg * power)
    else:
        amount = 0

    return amount


class CombatTurnManager:
    def __init__(self, session):
        self.session = session
        self.party = session.members
        self.enemies = session.enemies
        self.turn_order = self._build_turn_order()
        self.turn_index = 0
        self.phase = "players"
        self.round_number = 1

        # Cache for frequently accessed data
        self._alive_cache = {}
        self._cache_invalidated = True

        # Has Boss moved this turn?
        self.boss_turn = False

    def _build_turn_order(self):
        """Build the initial turn order with players first, then enemies"""
        turn_order = []

        # Add players
        for player_id in self.party:
            turn_order.append({"type": "player", "id": player_id})

        # Add enemies with their index
        for i, enemy in enumerate(self.enemies):
            turn_order.append({"type": "enemy", "id": i})

        return turn_order

    def add_enemy(self, enemy_data):
        """Add a new enemy during combat and update turn order"""
        # Add enemy to enemies list
        self.enemies.append(enemy_data)
        enemy_index = len(self.enemies) - 1

        # Add to turn order after current turn
        new_turn_entry = {"type": "enemy", "id": enemy_index}

        # Insert after current turn so it gets a chance to act
        insert_position = self.turn_index + 1
        if insert_position >= len(self.turn_order):
            self.turn_order.append(new_turn_entry)
        else:
            self.turn_order.insert(insert_position, new_turn_entry)

        # Invalidate cache
        self.invalidate_cache()

        return enemy_index

    def remove_dead_enemies_from_turn_order(self):
        """Remove dead enemies from turn order and adjust indices"""
        alive_enemies = []
        enemy_index_map = {}  # Old index -> New index

        # Build list of alive enemies and create index mapping
        for i, enemy in enumerate(self.enemies):
            if enemy["hp"] > 0:
                enemy_index_map[i] = len(alive_enemies)
                alive_enemies.append(enemy)

        # Update enemies list
        self.enemies = alive_enemies

        # Update turn order
        new_turn_order = []
        for turn_entry in self.turn_order:
            if turn_entry["type"] == "player":
                new_turn_order.append(turn_entry)
            elif turn_entry["type"] == "enemy":
                old_index = turn_entry["id"]
                if old_index in enemy_index_map:
                    new_turn_order.append({
                        "type": "enemy",
                        "id": enemy_index_map[old_index]
                    })
                # If enemy is dead, don't add to new turn order

        # Adjust current turn index if needed
        if self.turn_index >= len(new_turn_order):
            self.turn_index = 0

        self.turn_order = new_turn_order
        self.invalidate_cache()

    def invalidate_cache(self):
        """Call this when health/enemy states change"""
        self._cache_invalidated = True

    def get_alive_players(self):
        """Cached version of alive players check"""
        if self._cache_invalidated:
            self._alive_cache['players'] = [
                pid for pid in self.party
                if db.dget(str(pid), "stats").get("Health", 0) > 0
            ]
            self._cache_invalidated = False
        return self._alive_cache['players']


    def get_current_actor(self):
        """Get the current actor from turn order"""
        if not self.turn_order:
            return None

        current_turn = self.turn_order[self.turn_index]
        if current_turn["type"] == "player":
            return current_turn["id"]
        else:  # enemy
            return current_turn["id"]

    def get_current_actor_type(self):
        """Get whether current actor is player or enemy"""
        if not self.turn_order:
            return None
        return self.turn_order[self.turn_index]["type"]

    def reset_for_next_wave(self):
        """Reset for next wave"""
        self.enemies = self.session.enemies
        self.turn_order = self._build_turn_order()
        self.turn_index = 0
        self.round_number = 1
        self.invalidate_cache()

    def advance_turn(self):
        """Advance to next turn, skipping dead actors"""
        loop_count = 0
        max_loops = len(self.turn_order) * 2  # Prevent infinite loops

        while loop_count < max_loops:
            self.turn_index = (self.turn_index + 1) % len(self.turn_order)

            # Check if we completed a full round
            if self.turn_index == 0:
                self.round_number += 1
                # Clean up dead enemies at start of new round
                self.remove_dead_enemies_from_turn_order()
                if not self.turn_order:  # No actors left
                    break

            actor_type = self.get_current_actor_type()
            actor_id = self.get_current_actor()

            if actor_id is None:
                break

            if self.is_actor_alive(actor_type, actor_id):
                break

            loop_count += 1

        # Update phase
        actor_type = self.get_current_actor_type()
        self.phase = "players" if actor_type == "player" else "enemies"

    def is_actor_alive(self, actor_type, actor_id):
        """Check if an actor is alive"""
        if actor_type == "player":
            stats = db.dget(str(actor_id), "stats") or {}
            return stats.get("Health", 0) > 0
        else:  # enemy
            if actor_id < len(self.enemies):
                return self.enemies[actor_id]["hp"] > 0
            return False

    def is_combat_over(self):
        """Check if combat is over"""
        # Check enemies first (usually fewer)
        if all(enemy["hp"] <= 0 for enemy in self.enemies):
            return True

        # Check players
        if all(db.dget(str(player), "stats").get("Health", 0) <= 0 for player in self.party):
            return True

        return False

    def get_target_by_strategy(self, strategy="lowest_hp"):
        """Get target based on strategy (lowest_hp, random, highest_hp)"""
        alive_targets = self.get_alive_players()

        if not alive_targets:
            return None

        if strategy == "lowest_hp":
            return min(alive_targets, key=lambda pid: db.dget(str(pid), "stats").get("Health", 0))
        elif strategy == "highest_hp":
            return max(alive_targets, key=lambda pid: db.dget(str(pid), "stats").get("Health", 0))
        else:  # random
            return random.choice(alive_targets)


def get_user_stats(user_id):
    """Optimized stats retrieval with fallback"""
    return db.dget(user_id, "stats") or {}

def calculate_boss_damage(turn_manager, skill_power=0.3):
    """Calculate boss damage based on party's total max health"""
    party_health = 0
    for pid in turn_manager.party:
        player_stats = db.dget(str(pid), "stats")
        if player_stats:
            party_health += player_stats.get("MaxHealth", 0)

    boss_dmg = int(party_health * skill_power)
    return boss_dmg

def create_hp_bar(current_hp, max_hp, length=10):
    """Optimized HP bar creation"""
    if max_hp <= 0:
        return "N/A"

    percentage = max(0, min(current_hp / max_hp, 1))  # Clamp between 0 and 1
    filled = int(percentage * length)
    empty = length - filled

    bar = f"{'<:hpfull:1389208660906868890>' * filled}{'<:hpmissing:1389208658071781518>' * empty}"
    return f"{bar} {current_hp}/{max_hp} HP"


def create_mana_bar(current_mana, max_mana, length=10):
    """Renamed and optimized mana bar"""
    if max_mana <= 0:
        return ""

    percentage = max(0, min(current_mana / max_mana, 1))
    filled = int(percentage * length)
    empty = length - filled

    bar = f"{'<:mana1:1392789954278588447>' * filled}{'<:hpmissing:1389208658071781518>' * empty}"
    return f"{bar} {current_mana}/{max_mana} MP"


def create_green_bar(current_hp, max_hp, length=10):
    """Green HP bar variant"""
    if max_hp <= 0:
        return "N/A"

    percentage = max(0, min(current_hp / max_hp, 1))
    filled = int(percentage * length)
    empty = length - filled

    bar = f"{'<:hp1:1389485623793942621>' * filled}{'<:hpmissing:1389208658071781518>' * empty}"
    return f"{bar} {current_hp}/{max_hp} HP"


def update_user_hp(user_id, hp_change):
    """Optimized HP update with proper clamping"""
    stats = db.dget(user_id, "stats") or {}
    current_hp = stats.get("CurrentHP", 0)
    max_hp = stats.get("Health", 0)

    new_hp = max(0, min(current_hp + hp_change, max_hp))
    stats["CurrentHP"] = new_hp
    db.dadd(user_id, ("stats", stats))
    return new_hp


async def handle_enemy_action(enemy, turn_manager, channel, target_strategy="lowest_hp"):
    """Consolidated enemy action handler"""
    enemy_name = enemy["name"]

    # Check if enemy is alive
    if enemy["hp"] <= 0:
        await channel.send(f"☠️ **{enemy_name}** is defeated and cannot act.")
        return False

    # Check stun status
    if any(debuff["name"] == "stun" for debuff in enemy.get("debuffs", [])):
        await channel.send(f"💫 **{enemy_name}** is stunned and skips their turn!")
        await apply_status_effects(enemy, channel)
        return True

    # Apply status effects
    await apply_status_effects(enemy, channel)

    # Check if died from status effects
    if enemy["hp"] <= 0:
        await channel.send(f"☠️ **{enemy_name}** was defeated by status effects!")
        return False

    # Get target based on strategy
    target_id = turn_manager.get_target_by_strategy(target_strategy)
    if not target_id:
        await turn_manager.session.end_dungeon("☠️ The party was wiped out!")
        return False

    enemy_skills = enemy.get("skills", [])
    if enemy_skills:
        # Enemy has skills - choose one randomly
        chosen_skill = random.choice(enemy_skills)
        await process_skill_effect(
            skill=chosen_skill,
            caster=enemy,
            target_id=target_id,
            turn_manager=turn_manager,
            channel=channel
        )
    else:
        # Default basic attack for enemies without skills
        await handle_basic_enemy_attack(enemy, target_id, turn_manager, channel)

    return True

async def handle_basic_enemy_attack(enemy, target_id, turn_manager, channel):
    """Handle basic enemy attack (for enemies without skills)"""
    member = channel.guild.get_member(target_id)
    stats = db.dget(str(target_id), "stats") or {}

    # Check dodge
    if check_dodge(stats):
        embed = discord.Embed(
            title=f"**{enemy['name']}** attacks!",
            description=f"**{member.display_name if member else 'Player'} dodged the attack!**",
            color=discord.Color.green()
        )
        await channel.send(embed=embed)
        return

    # Apply damage
    damage = enemy["power"]
    new_hp = apply_damage_to_player(target_id, damage)

    embed = discord.Embed(
        title=f"**{enemy['name']}** attacks!",
        description=f"<@{target_id}> takes **{damage}** damage!",
        color=discord.Color.red()
    )

    # Add HP bar
    max_hp = stats.get("MaxHealth", 100)
    hp_bar = create_green_bar(new_hp, max_hp)
    embed.add_field(
        name=f"{member.display_name if member else 'Player'}'s HP",
        value=hp_bar,
        inline=False
    )

    await channel.send(embed=embed)

    if new_hp <= 0:
        await channel.send(f"☠️ <@{target_id}> has fallen in battle!")

async def process_skill_effect(skill, caster, target_id, turn_manager, channel):
    """Process skill effects with different targets and effects"""
    skill_name = skill.get("name", "Unknown Skill")
    skill_power = skill.get("power", 0.1)
    skill_effect = skill.get("effect", "damage")
    skill_target = skill.get("target", "single")
    dialogue = skill.get("dialogue", "")

    caster_name = caster.get("name", "Unknown")
    results = []

    # Determine targets based on skill_target
    if skill_target == "single":
        targets = [target_id] if target_id else []
    elif skill_target == "all":
        if skill_effect in ["heal", "buff"]:
            # Heal/buff all allies (enemies in this case)
            targets = [enemy for enemy in turn_manager.enemies if enemy["hp"] > 0]
        else:
            # Damage all players
            targets = turn_manager.get_alive_players()
    elif skill_target == "self":
        targets = [caster]
    else:
        targets = [target_id] if target_id else []

    # Apply effects based on skill_effect
    if skill_effect == "damage":
        # FIXED: Better damage calculation
        if skill.get("base_damage"):
            # Use explicit base damage if provided
            damage = int(skill["base_damage"] * skill_power)
        elif caster.get("is_boss"):
            # Boss damage calculation - scale with party health
            damage = calculate_boss_damage(turn_manager, skill_power)
        else:
            # Regular enemy damage
            base_damage = caster.get("power", 10)
            damage = int(base_damage * skill_power)

        print(f"[DEBUG] Damage calculation: base={caster.get('power', 10)}, power={skill_power}, final={damage}")

        if skill_target == "all":
            # Damage all alive players
            for player_id in targets:
                if isinstance(player_id, int):  # Player target
                    new_hp = apply_damage_to_player(player_id, damage)
                    results.append(f"<@{player_id}> took **{damage}** damage!")
                    print(f"[DEBUG] Applied {damage} damage to player {player_id}, new HP: {new_hp}")
        else:
            # Damage single target
            if isinstance(target_id, int):  # Player target
                new_hp = apply_damage_to_player(target_id, damage)
                results.append(f"<@{target_id}> took **{damage}** damage!")
                print(f"[DEBUG] Applied {damage} damage to player {target_id}, new HP: {new_hp}")

    elif skill_effect == "heal":
        if skill_target == "all":
            for enemy in targets:
                if isinstance(enemy, dict) and "hp" in enemy:  # Enemy target
                    max_hp = enemy.get("base_hp", 100)
                    heal_amount = int(max_hp * skill_power)
                    enemy["hp"] = min(enemy["hp"] + heal_amount, max_hp)
                    results.append(f"**{enemy['name']}** healed for **{heal_amount}** HP!")
        elif skill_target == "self":
            max_hp = caster.get("base_hp", 100)
            heal_amount = int(max_hp * skill_power)
            caster["hp"] = min(caster["hp"] + heal_amount, max_hp)
            results.append(f"**{caster_name}** healed for **{heal_amount}** HP!")

    elif skill_effect == "summon":
        summoned = caster.get("summons", [])
        for summon_data in summoned:
            # Create a copy of the summon data to avoid modifying the original
            summon_copy = summon_data.copy()

            # Add the summon using the new method
            enemy_index = turn_manager.add_enemy(summon_copy)
            results.append(f"**{caster_name}** summoned **{summon_copy['name']}**!")

    elif skill_effect == "buff":
        # Apply buffs to targets (implementation depends on your buff system)
        buff_stat = skill.get("buff_stat", "Strength")
        buff_multiplier = skill.get("buff_multiplier", 1.2)
        buff_duration = skill.get("duration", 3)

        for target in targets:
            if isinstance(target, int):  # Player target
                buff_player(str(target), buff_stat, buff_multiplier, buff_duration)
                results.append(f"<@{target}> gained **{buff_stat}** buff!")

    elif skill_effect == "debuff":
        # Apply debuffs to targets
        debuff_name = skill.get("debuff_name", "poison")
        debuff_value = skill.get("debuff_value", 5)
        debuff_duration = skill.get("duration", 3)

        for target in targets:
            if isinstance(target, int):  # Player target
                user_id_str = str(target)
                stats = db.dget(user_id_str, "stats") or {}
                if "debuffs" not in stats:
                    stats["debuffs"] = []

                # Add debuff
                stats["debuffs"].append({
                    "name": debuff_name,
                    "value": debuff_value,
                    "duration": debuff_duration
                })
                db.dadd(user_id_str, ("stats", stats))
                results.append(f"<@{target}> was afflicted with **{debuff_name}**!")

    # Create and send embed
    embed = discord.Embed(
        title=f"✨ **{caster_name}** used {skill_name} ✨",
        description=dialogue if dialogue else "\n".join(results),
        color=discord.Color.red()
    )

    if not dialogue and results:
        embed.add_field(name="Effects", value="\n".join(results), inline=False)

    # FIXED: Add boss HP bar to show current status
    if caster.get("is_boss"):
        max_hp = caster.get("base_hp", 0)
        hp_bar = create_hp_bar(caster["hp"], max_hp)
        embed.add_field(name=f"{caster_name} HP", value=hp_bar, inline=False)

    await channel.send(embed=embed)
    print(f"[DEBUG] Skill effect complete. Results: {results}")
    return results

def apply_damage_to_player(player_id, damage):
    """Centralized damage application"""
    user_id_str = str(player_id)
    stats = db.dget(user_id_str, "stats") or {}
    current_hp = stats.get("Health", 100)
    new_hp = max(current_hp - int(damage), 0)
    stats["Health"] = new_hp
    db.dadd(user_id_str, ("stats", stats))
    return new_hp


async def start_turn(channel: discord.TextChannel, turn_manager: CombatTurnManager):
    """Main turn management function"""
    # Check if combat is over first
    if turn_manager.is_combat_over():
        await handle_combat_end(turn_manager, channel)
        return

    actor_type = turn_manager.get_current_actor_type()
    actor_id = turn_manager.get_current_actor()

    if actor_id is None:
        await channel.send("❌ No valid actors found!")
        return

    if actor_type == "player":
        await handle_player_turn(actor_id, turn_manager, channel)
    else:  # enemy
        if actor_id < len(turn_manager.enemies):
            enemy = turn_manager.enemies[actor_id]
            success = await handle_enemy_action(enemy, turn_manager, channel)

            # ALWAYS advance turn after enemy action (whether successful or not)
            turn_manager.advance_turn()
            await asyncio.sleep(1.2)

            # Continue to next turn
            await start_turn(channel, turn_manager)
        else:
            # Enemy index out of bounds, advance turn
            turn_manager.advance_turn()
            await asyncio.sleep(1.2)
            await start_turn(channel, turn_manager)


async def handle_player_turn(player_id, turn_manager, channel):
    """Handle player turn logic"""
    stats = db.dget(str(player_id), "stats") or {}

    # Check if player is dead
    if stats.get("Health", 0) <= 0:
        await channel.send(f"☠️ <@{player_id}> is defeated and cannot act.")
        turn_manager.advance_turn()
        await asyncio.sleep(1.5)
        await start_turn(channel, turn_manager)
        return

    # Check stun
    if any(debuff["name"] == "stun" for debuff in stats.get("debuffs", [])):
        await channel.send(f"💫 <@{player_id}> is stunned and skips their turn!")
        await apply_player_status_effects(player_id, channel)
        turn_manager.advance_turn()
        await asyncio.sleep(1.2)
        await start_turn(channel, turn_manager)
        return

    # Apply status effects
    await apply_player_status_effects(player_id, channel)

    # Check win condition
    if turn_manager.is_combat_over():
        await handle_combat_end(turn_manager, channel)
        return

    # Display enemies
    await display_enemies(turn_manager, channel)

    # Show player UI
    await show_player_ui(player_id, turn_manager, channel)


async def handle_combat_end(turn_manager, channel):
    """Handle combat end scenarios"""
    session = turn_manager.session
    session.stage += 1

    if session.stage < session.max_waves:
        await channel.send(f"✅ Wave {session.stage} cleared! Get ready for the next one...")
        await asyncio.sleep(5)
        session.enemies = generate_enemy_wave(len(session.members))
        turn_manager.reset_for_next_wave()
        await start_turn(channel, turn_manager)
    else:
        await session.give_rewards()
        await session.end_dungeon("🎉 The party has defeated all waves!")


async def display_enemies(turn_manager, channel):
    """Display current enemy status"""
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
            bar = f"{name}\n{create_hp_bar(hp, max_hp)}"

        enemy_display += f"{bar}\n\n"

    # Truncate if too long
    if len(enemy_display) > 1024:
        enemy_display = enemy_display[:1000] + "\n... (truncated)"

    enemy_embed.add_field(name="Enemies", value=enemy_display, inline=False)
    await channel.send(embed=enemy_embed)
    await asyncio.sleep(1.5)


async def show_player_ui(player_id, turn_manager, channel):
    """Show player action UI"""
    user_id = str(player_id)
    user_class = db.dget(user_id, "class")
    player_skills = skills[user_class]
    member = channel.guild.get_member(player_id)
    username = member.display_name if member else f"User {player_id}"

    # Create combat view
    view = CombatView(session=turn_manager.session, player_id=player_id, player_skills=player_skills)

    # Get player stats
    user_stats = db.dget(user_id, "stats")
    user_max_hp = user_stats.get("MaxHealth", 0)
    user_max_mana = user_stats.get("MaxMana", 0)
    user_current_hp = user_stats.get("Health", 0)
    user_current_mana = user_stats.get("Mana", 0)

    # Create embeds
    hp_bar = create_hp_bar(user_current_hp, user_max_hp)
    mana_bar = create_mana_bar(user_current_mana, user_max_mana)

    user_embed = discord.Embed(
        title=f"{username}'s current stats",
        description=f"{hp_bar}\n{mana_bar}",
        color=discord.Color.blue()
    )

    action_embed = discord.Embed(
        title=f"🎯 {username}'s Turn",
        description="Choose your action below.",
        color=discord.Color.gold()
    )

    await channel.send(embed=user_embed)
    await channel.send(embed=action_embed, view=view)
    await view.wait()

    # Process end of turn
    process_buffs(user_id)
    turn_manager.advance_turn()
    await asyncio.sleep(1.2)
    await start_turn(channel, turn_manager)


async def apply_player_status_effects(player_id: int, channel: discord.TextChannel):
    """Apply status effects to a player"""
    user_id_str = str(player_id)
    stats = db.dget(user_id_str, "stats") or {}

    if "debuffs" not in stats:
        stats["debuffs"] = []

    # Create temporary entity for status system
    player_entity = {
        "name": f"<@{player_id}>",
        "hp": stats.get("Health", 100),
        "debuffs": stats.get("debuffs", [])
    }

    # Apply effects
    updated_entity = await apply_status_effects(player_entity, channel)

    # Update stats
    stats["Health"] = max(updated_entity["hp"], 0)
    stats["debuffs"] = updated_entity["debuffs"]
    db.dadd(user_id_str, ("stats", stats))

    # Check death
    if stats["Health"] <= 0:
        await channel.send(f"☠️ <@{player_id}> was defeated by status effects!")
        await asyncio.sleep(1.2)


# Helper functions
def apply_damage_with_effects(target_entity, damage, effect_name=None, effect_value=0, effect_duration=2):
    """Apply damage and optionally add a status effect"""
    target_entity["hp"] -= damage
    if effect_name:
        apply_status_effect(target_entity, effect_name, effect_value, effect_duration)
    return target_entity


def heal_player(user_id: str, power: float):
    """Heal a player using centralized healing"""
    stats = db.dget(user_id, "stats") or {}
    heal_amount, updated_stats = apply_healing(stats, power)
    db.dadd(user_id, ("stats", updated_stats))
    return heal_amount


def buff_player(user_id: str, stat: str, multiplier: float, duration: int):
    """Apply a buff to a player"""
    apply_buff(user_id, stat, multiplier, duration)


def get_player_effective_stat(user_id: str, stat_name: str) -> int:
    """Get player's effective stat value including buffs"""
    return get_effective_stat(user_id, stat_name)