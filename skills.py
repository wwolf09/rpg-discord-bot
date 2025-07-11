skills = {
    "swordsman": {
        "Bash": {
            "desc": "Deals damage and has a chance to stun.",
            "mana_cost": 0,
            "type": "physical",
            "power": 1.0,
            "effect": "stun",
            "stat": "Strength"
        },
        "Power Strike": {
            "desc": "A heavy hit that deals increased damage.",
            "mana_cost": 0,
            "type": "physical",
            "power": 1.3,
            "stat": "Strength"
        },
        "Battle Cry": {
            "desc": "Increases your Strength for 3 turns at the cost of HP.",
            "mana_cost": 0,
            "hp_cost": 0.2,  # 20% of max HP
            "type": "buff",
            "effect": "STR+10%",
            "stat": "Strength",
            "multiplier": 0.10,
            "duration": 3,
            "target": "self"
        }
    },
    "mage": {
        "Fireball": {
            "desc": "Hurls a ball of fire. Burns over time.",
            "mana_cost": 70,
            "type": "magic",
            "power": 1.3,
            "effect": "burn",
            "stat": "MagicDmg",
            "dot": {"value": 10, "duration": 3}
        },
        "Arcane Shield": {
            "desc": "Protects you with a magical barrier.",
            "mana_cost": 30,
            "type": "buff",
            "effect": "absorb",
            "stat": "MagicDmg",
            "absorb_percent": 0.2,
            "duration": 2
        },
        "Magic Missile": {
            "desc": "Simple magic dart. Reliable and cheap.",
            "mana_cost": 40,
            "type": "magic",
            "power": 1.2,
            "stat": "MagicDmg"
        }
    },
    "rogue": {
        "Backstab": {
            "desc": "Deals high damage if used first.",
            "mana_cost": 0,
            "type": "physical",
            "power": 1.8,
            "effect": "first_strike_bonus",
            "stat": "Strength"
        },
        "Smoke Bomb": {
            "desc": "Increases dodge chance for 2 turns.",
            "mana_cost": 0,
            "type": "buff",
            "effect": "AGI+50%",
            "stat": "Agility",
            "target": "self",
            "multiplier": 0.5,
            "duration": 2
        },
        "Poison Blade": {
            "desc": "Poisons enemy for 3 turns.",
            "mana_cost": 0,
            "type": "debuff",
            "effect": "poison",
            "stat": "DOT",
            "target": "self",
            "dot": {"value": 8, "duration": 3}
        }
    },
    "healer": {
        "Heal": {
            "desc": "Restores a moderate amount of HP.",
            "mana_cost": 50,
            "type": "healing",
            "power": 0.3,
            "stat": "heal"
        },
        "Blessing": {
            "desc": "Increases party's Strength temporarily.",
            "mana_cost": 30,
            "type": "buff",
            "effect": "STR+15%",
            "stat": "Strength",
            "target": "all",
            "multiplier": 0.15,
            "duration": 3
        },
        "Smite": {
            "desc": "Holy damage to evil beings.",
            "mana_cost": 40,
            "type": "magic",
            "power": 1.0,
            "stat": "MagicDmg"
        }
    }
}
