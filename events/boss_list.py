def create_boss():
    return {
        "name": "Azaroth, the Flame Tyrant",
        "base_hp": 3000,
        "hp": 3000,
        "debuffs": [],
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
                "dialogue": " '*COME! Let us show our wrath.*'",
                "target": None
            }
        ],
        "cooldowns": {0: 0, 1: 0, 2: 0},
        "turn_count": 0,
        "is_boss": True,
        "summons": [
            {
                "name": "Dark Mage",
                "base_hp": 100,
                "hp": 100,
                "power": 10,  # Fixed
                "debuffs": [],  # Added
                "skills": [
                    {
                        "name": "Flaming Heal",
                        "effect": "heal",
                        "power": 2.0,
                        "target": "all"
                    }
                ],
                "is_summon": True,
            },
            {
                "name": "Dark Knight",
                "base_hp": 500,
                "hp": 500,
                "power": 2,  # Fixed
                "debuffs": [],  # Added
                "difficulty": "easy",
                "is_summon": True
            },
        ],
    }