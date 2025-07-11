def create_boss():
    return {
        "name": "Azaroth, the Flame Tyrant",
        "base_hp": 3000,
        "hp": 3000,
        "skills": [
            {
                "name": "Inferno Burst",
                "type": "magic",
                "power": 1.2,
                "effect": "burn",
                "cooldown": 2,
                "dialogue": "You shall **BURN**!",
                "target": "single"
            },
            {
                "name": "Flame Heal",
                "type": "buff",
                "effect": "heal",
                "power": 0.3,
                "cooldown": 3,
                "dialogue": "I am not to be meddled with.",
                "target": "self"
            },
            {
                "name": "Summon Firelings",
                "type": "summon",
                "effect": "summon",
                "cooldown": 5,
                "dialogue": "Summons 2 Fireling minions to aid him.",
                "target": None
            }
        ],
        "cooldowns": {0: 0, 1: 0, 2: 0},  # Track cooldowns for skills
        "turn_count": 0,
        "debuffs": [],
        "is_boss": True,
        "summons": [  # Changed from {} to []
            {
                "name": "Dark Mage",
                "base_hp": 100,
                "hp": 100,
                "base_power": 0,
                "skills": {
                    "name": "Flaming Heal",
                    "effect": "heal",
                    "power": 2.0,
                    "target": "all"
                }
            },
            {
                "name": "Dark Knight",
                "base_hp": 500,
                "hp": 500,
                "base_power": 2,
                "difficulty": "easy"
            },
        ],
    }
