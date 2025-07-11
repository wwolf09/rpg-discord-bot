# status_effects.py
import random
import asyncio
from db import db

async def apply_status_effects(entity, channel=None):
    """Applies ongoing effects like burn, poison, or checks for stun."""
    effects_to_remove = []

    for effect in entity.get("debuffs", []):
        name = effect["name"]
        duration = effect.get("duration", 0)

        if name == "burn":
            damage = effect.get("value", 5)
            entity["hp"] -= damage
            if channel:
                await channel.send(f"🔥 {entity['name']} takes {damage} burn damage!")

        elif name == "poison":
            damage = effect.get("value", 3)
            entity["hp"] -= damage
            if channel:
                await channel.send(f"☠️ {entity['name']} takes {damage} poison damage!")

        elif name == "stun":
            if channel:
                await channel.send(f"💫 {entity['name']} is stunned and skips their turn!")

        # Reduce duration
        effect["duration"] -= 1
        if effect["duration"] <= 0:
            effects_to_remove.append(effect)

    for expired in effects_to_remove:
        entity["debuffs"].remove(expired)

    return entity

def check_dodge(user_stats):
    agility = user_stats.get("Agility", 0)
    dodge_chance = min(agility * 0.01, 0.5)
    return random.random() < dodge_chance

def apply_healing(user_stats, power):
    max_hp = user_stats.get("MaxHealth", 100)
    heal_amount = int(max_hp * power)
    user_stats["Health"] = min(user_stats["Health"] + heal_amount, max_hp)
    return heal_amount, user_stats

def apply_status_effect(target_entity, effect_name, value=0, duration=2):
    if "debuffs" not in target_entity:
        target_entity["debuffs"] = []

    target_entity["debuffs"].append({
        "name": effect_name,
        "value": value,
        "duration": duration
    })

#################################

def apply_buff(user_id: str, stat: str, multiplier: float, duration: int):
    stats = db.dget(user_id, "stats") or {}
    buffs = stats.get("buffs", [])

    buffs.append({
        "stat": stat,
        "multiplier": multiplier,
        "duration": duration
    })

    stats["buffs"] = buffs
    db.dadd(user_id, ("stats", stats))

def process_buffs(user_id: str):
    stats = db.dget(user_id, "stats") or {}
    buffs = stats.get("buffs", [])
    active_buffs = []

    for buff in buffs:
        buff["duration"] -= 1
        if buff["duration"] > 0:
            active_buffs.append(buff)

    stats["buffs"] = active_buffs
    db.dadd(user_id, ("stats", stats))

def get_effective_stat(user_id: str, stat_name: str) -> int:
    stats = db.dget(user_id, "stats") or {}
    base_value = stats.get(stat_name, 0) + int(db.dget(user_id, "equipped_weapon")["data"].get("Damage"))
    total_multiplier = 1.0

    for buff in stats.get("buffs", []):
        if buff["stat"] == stat_name:
            total_multiplier *= buff["multiplier"]

            print(total_multiplier)
            print(buff["multiplier"])

    return int(base_value * total_multiplier)

""" HOW TO USE 
# Applying 10% Strength buff for 3 turns
apply_buff(user_id="123456", stat="Strength", multiplier=1.10, duration=3)

# During damage calc
strength = get_effective_stat("123456", "Strength")
"""
