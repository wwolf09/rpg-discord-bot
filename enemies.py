import random

base_enemies = [
    {"name": "Goblin", "base_hp": 90, "base_power": 12, "difficulty": "easy"},
    {"name": "Skeleton", "base_hp": 85, "base_power": 15, "difficulty": "easy"},
    {"name": "Wraith", "base_hp": 80, "base_power": 18, "difficulty": "easy"},
    {"name": "Slime", "base_hp": 120, "base_power": 10, "difficulty": "easy"},
    {"name": "Dark Bat", "base_hp": 75, "base_power": 14, "difficulty": "easy"},
]

boss_azaroth = {
    "name": "Dreadfiend Azaroth",
    "base_hp": 2500,
    "hp": 2500,
    "skills": {
        "Soul Crush": {
            "desc": "Crushes your soul for heavy damage.",
            "type": "magic",
            "power": 1.8,
            "effect": None,
            "stat": "MagicDmg"
        },
        "Flame Whip": {
            "desc": "Whips the target, burning them.",
            "type": "magic",
            "power": 1.5,
            "effect": "burn",
            "stat": "MagicDmg"
        },
        "Shadow Bind": {
            "desc": "Stuns you with shadowy chains.",
            "type": "magic",
            "power": 1.3,
            "effect": "stun",
            "stat": "MagicDmg"
        }
    },
    "debuffs": []
}


difficulty_multiplier = {
    "easy": 1.0,
    "medium": 1.5,
    "hard": 2.0,
}

def calculate_scaled_rewards(enemies):
    total_xp = 0
    total_gold = 0
    for enemy in enemies:
        if enemy.get("hp", 0) <= 0:
            base = next((b for b in base_enemies if b["name"] == enemy["name"]), None)
            if base:
                diff = base.get("difficulty", "easy")
                mult = difficulty_multiplier.get(diff, 1.0)

                xp = int((enemy.get("base_hp", 100) + enemy.get("power", 20)) * mult)
                gold = int((enemy.get("base_hp", 100) + enemy.get("power", 20)) * mult * 0.5)

                total_xp += xp
                total_gold += gold
    return total_xp, total_gold

def generate_enemy_wave(party_size: int):
    if party_size <= 3:
        wave_size = random.randint(1, 3)
    elif party_size <= 5:
        wave_size = random.randint(2, 4)
    else:
        wave_size = random.randint(3, 5)

    total_hp = 180 * party_size
    total_power = 35 * party_size

    selected_enemies = random.sample(base_enemies * 2, k=wave_size)  # allow duplicates if needed

    enemies = []
    for i in range(wave_size):
        enemy_template = selected_enemies[i % len(base_enemies)]
        share = 1 / wave_size
        scaled_hp = int(enemy_template["base_hp"] + total_hp * share)
        scaled_power = int(enemy_template["base_power"] + (total_power * share / wave_size))

        enemies.append({
            "name": enemy_template["name"],
            "hp": scaled_hp,
            "power": scaled_power,
            "base_hp": scaled_hp,
            "buffs": [],
            "debuffs": [],
            "turn_counter": 0
        })

    return enemies
