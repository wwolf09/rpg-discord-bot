quiz_questions = [
    {
        "question": "In battle, your weapon of choice is...",
        "choices": {
            "A": {"text": "A broadsword or axe - I like feeling the weight of my hits.", "swordsman": 2},
            "B": {"text": "A staff, tome, or orb - knowledge is power.", "mage": 2},
            "C": {"text": "Daggers or anything throwable — fast, light, and lethal.", "rogue": 2},
            "D": {"text": "A charm, relic, or holy symbol — to protect and heal.", "healer": 2},
        }
    },
    {
        "question": "Your party is ambushed! What’s your instinct?",
        "choices": {
            "A":{"text": "Evade and strike from the shadows.", "rogue": 2} ,
            "B": {"text": "Heal the injured and support your team.", "healer": 2},
            "C": {"text": "Charge in and protect your allies.", "swordsman": 2},
            "D": {"text": "Analyze and prepare a counter spell.", "mage": 2},
        }
    },
    {
        "question": "What motivates you the most?",
        "choices": {
            "A": {"text": "Honor and glory in battle.", "swordsman": 2},
            "B": {"text": "Freedom and independence.", "rogue": 2} ,
            "C": {"text": "Pursuit of arcane knowledge.", "mage": 2},
            "D": {"text": "Helping and healing others.", "healer": 2},
        }
    },
    {
        "question": "Choose a downtime activity.",
        "choices": {
            "A": {"text": "Sparring or training drills.", "swordsman": 2},
            "B": {"text": "Studying runes or alchemy.", "mage": 2},
            "C": {"text": "Tending to the sick or injured.", "healer": 2},
            "D": {"text": "Exploring secret paths.", "rogue": 2},
        }
    },
    {
        "question": "A powerful relic lies ahead, but it’s cursed. What do you do?",
        "choices": {
            "A": {"text": "Smash the relic. Not worth the risk.", "swordsman": 2},
            "B": {"text": "Cleanse or purify it.", "healer": 2},
            "C": {"text": "Steal it and sell it.", "rogue": 2},
            "D": {"text": "Study it, could be useful.", "mage": 2},
        }
    },
    {
        "question": "How would others describe you in the party?",
        "choices": {
            "A": {"text": "Mysterious and intelligent.", "mage": 2},
            "B": {"text": "Brave and dependable.", "swordsman": 2},
            "C": {"text": "Quiet but deadly.", "rogue": 2},
            "D": {"text": "Gentle and wise.", "healer": 2},
        }
    },
]

subclasses = {
    "swordsman": ["Paladin", "Berserker"],
    "mage": ["Cryomancer", "Stormcaller"],
    "rogue": [ "Gunslinger", "Sniper"],
    "healer": ["Cleric", "Druid", "Bard"]
}

classes = {
    "swordsman": {
        "MaxHealth": 180,             # More HP-based
        "Health": 180,
        "Strength": 0,
        "MagicDmg": 0,
        "Mana": 0,
        "MaxMana": 0,
        "CritChance": 5,           # Slight crit chance
        "CritDmg": 1.5,            # Default crit multiplier
        "Agility": 20,
        "Armor": 30,               # Needs armor slot
        "ManaRegen": 0,
        "HPRegen": 5,              # Passive HP regen (small)
        "Faith": 0,
        "Weapon": "Rusty Sword"
    },

    "mage": {
        "MaxHealth": 100,
        "Health": 100,
        "Strength": 0,
        "MagicDmg": 0,           # More magic scaling
        "Mana": 500,
        "MaxMana": 500,
        "ManaRegen": 15,           # Needs mana regen
        "CritChance": 10,          # Moderate crit
        "CritDmg": 1.5,
        "Agility": 10,
        "Armor": 5,                # Fragile
        "HPRegen": 0,
        "Faith": 10,
        "Weapon": "Worn Out Staff"
    },

    "rogue": {
        "MaxHealth": 120,
        "Health": 120,
        "Strength": 0,
        "MagicDmg": 0,
        "Mana": 0,
        "MaxMana": 0,
        "CritChance": 30,          # High crit chance
        "CritDmg": 2.0,            # Needs crit dmg stats
        "Agility": 40,             # More agility-based
        "Armor": 10,
        "ManaRegen": 0,
        "HPRegen": 2,
        "Faith": 5,
        "Weapon": "Rusty Daggers"
    },

    "healer": {
        "MaxHealth": 150,
        "Health": 150,
        "Strength": 0,
        "MagicDmg": 0,
        "Mana": 400,
        "MaxMana": 400,
        "ManaRegen": 10,
        "CritChance": 5,
        "CritDmg": 1.5,
        "Agility": 15,
        "Armor": 5,                # Less armor
        "HPRegen": 10,             # Needs HP regen
        "Faith": 40,               # Heals scale with Faith
        "Weapon": "Cracked Wand"
    }
}