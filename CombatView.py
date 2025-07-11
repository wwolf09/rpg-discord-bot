from dis import disco

from discord.ui import View, Button, Select
import discord
from db import db
from status_effects import apply_buff, get_effective_stat

def create_hp_bar(current_hp, max_hp, length=10):
    percentage = current_hp / max_hp
    filled = int(percentage * length)
    empty = length - filled
    bar = f"{'<:hpfull:1389208660906868890>' * filled}{'<:hpmissing:1389208658071781518>' * empty}"
    return f"{bar} {current_hp}/{max_hp} HP"

def calculate_skill_effect(user_stats, skill, user_id=None):
    power = skill.get("power", 1.0)
    skill_stat = skill.get("stat") # check if their stats are buffed for Strength or Magic
    print(f"[SKILL_STAT]: {skill_stat}")
    equipped_weapon = db.dget(user_id, "equipped_weapon")
    weapon_dmg = equipped_weapon["data"].get("Damage")
    total_dmg = get_effective_stat(user_id, skill_stat)
    print(f"[GET_EFFECTIVE_STAT]: {get_effective_stat(user_id, skill_stat)}")
    print(f"[WEAPON DMG]: {weapon_dmg}")
    print(f"[TOTAL DMG]: {total_dmg}")

    if skill["type"] in ["physical", "magic"]:
        amount = int(total_dmg * power)
        print(f"[POWER]: {power}")
    else:
        amount = 0

    return int(amount)

class AllySelectView(discord.ui.View):
    def __init__(self, session, skill_name, amount, parent_view):
        super().__init__(timeout=30)
        self.add_item(AllySelect(session, skill_name, amount, parent_view))

class AllySelect(discord.ui.Select):
    def __init__(self, session, skill_name, amount, parent_view):
        options = []
        for member_id in session.members:
            member_stats = db.dget(str(member_id), "stats") or {}
            hp = member_stats.get("Health", 100)
            max_hp = member_stats.get("MaxHealth", 100)
            member = session.client.get_user(member_id)
            label = member.display_name if member else f"User {member_id}"
            options.append(
                discord.SelectOption(label=f"{label} ({hp}/{max_hp})", value=str(member_id))
            )

        super().__init__(placeholder="Select ally to heal", options=options)
        self.skill_name = skill_name
        self.amount = amount
        self.session = session
        self.parent_view = parent_view

    async def callback(self, interaction: discord.Interaction):
        selected_id = str(self.values[0])
        stats = db.dget(selected_id, "stats") or {}
        max_hp = stats.get("MaxHealth", 100)
        current_hp = stats.get("Health", 100)
        healed = min(current_hp + self.amount, max_hp)
        stats["Health"] = healed
        db.dadd(selected_id, ("stats", stats))

        member = self.session.client.get_user(int(selected_id))
        embed = discord.Embed(
            title=f"{interaction.user.display_name} used {self.skill_name}",
            description=f"🩹 Healed **{member.display_name if member else 'an ally'}** for **{self.amount} HP**!",
            color=discord.Color.green()
        )
        embed.add_field(name="HP", value=create_hp_bar(healed, max_hp), inline=False)
        await interaction.response.send_message(embed=embed)
        self.parent_view.stop()


class CombatView(View):
    def __init__(self, session, player_id, player_skills):
        super().__init__(timeout=30)
        self.session = session
        self.player_id = player_id
        self.player_skills = player_skills

        self.chosen_skill = None
        self.selected_target = 0  # default: first enemy

        self.add_item(SkillSelect(self, player_skills))
        self.add_item(TargetSelect(self, session.enemies))
        self.add_item(UseButton(self))
        self.add_item(PassButton(self))

class SkillSelect(Select):
    def __init__(self, view, skills):
        options = [
            discord.SelectOption(label=skill_name, description=details["desc"])
            for skill_name, details in skills.items()
        ]
        super().__init__(placeholder="Use a Skill", options=options)
        self.view_ref = view
        self.skills = skills

    async def callback(self, interaction: discord.Interaction):
        if interaction.user.id != self.view_ref.player_id:
            await interaction.response.send_message("Not your turn!", ephemeral=True)
            return

        self.view_ref.chosen_skill = self.values[0]
        skill_name = self.values[0]
        skill = self.skills[skill_name]
        skill_mana_cost = skill.get("mana_cost") or 0

        effect = skill.get("effect")
        skill_type = skill["type"]

        user_id = str(self.view_ref.player_id)
        user_stats = db.dget(user_id, "stats") or {}
        user_mana = user_stats.get("Mana")
        print(f"[USER_MANA]: {user_mana}")

        if skill_mana_cost == 0:
            pass
        elif user_mana > skill_mana_cost:
            user_mana -= skill_mana_cost
            db.dset(user_id, ("stats", user_mana))
            print(f"[USER_MANA_AFTER]: {user_mana}")
            db.dump()
        elif user_mana < skill_mana_cost:
            await interaction.response.send_message(content="-# You don't have enough mana to cast this spell. Consider passing your turn.")
            return

        amount = calculate_skill_effect(user_stats, skill, user_id)
        print(amount)

        # HEALING SKILLS — allow targeting allies instead of enemies
        if skill_type == "healing":
            # If solo, just heal self
            if len(self.view_ref.session.members) <= 1:
                max_hp = user_stats.get("MaxHealth", 100)
                current_hp = user_stats.get("Health", 100)
                healed = min(current_hp + amount, max_hp)
                user_stats["Health"] = healed
                db.dadd(user_id, ("stats", user_stats))

                embed = discord.Embed(
                    title=f"{interaction.user.display_name} used {skill_name}",
                    description=f"🔮 Healed **yourself** for **{amount} HP**!",
                    color=discord.Color.green()
                )
                embed.add_field(name="HP", value=create_hp_bar(healed, max_hp), inline=False)
                await interaction.response.send_message(embed=embed)
                self.view_ref.stop()
                return

            # Else show dropdown to choose ally
            view = AllySelectView(self.view_ref.session, skill_name, amount, self.view_ref)
            await interaction.response.send_message("🩹 Choose a party member to heal:", view=view, ephemeral=True)
            await view.wait()
            return

        # ---------- PHYSICAL OR MAGIC DAMAGE ----------
        target = self.view_ref.session.enemies[self.view_ref.selected_target]
        max_hp = target.get("base_hp", 100)
        current_hp = target.get("hp", max_hp)

        embed = discord.Embed(
            title=f"{interaction.user.display_name} used {skill_name}",
            color=discord.Color.green()
        )

        if skill_type in ("physical", "magic"):
            target["hp"] = max(current_hp - amount, 0)
            embed.description = f"💥 Dealt **{amount}** damage to **{target['name']}**!"

            # Status effects
            if effect == "burn":
                target["debuffs"].append({"name": "burn", "duration": 3, "value": 10})
                embed.description += "\n🔥 Target is now **Burning** (10 dmg/turn for 3 turns)"
            elif effect == "poison":
                target["debuffs"].append({"name": "poison", "duration": 3, "value": 7})
                embed.description += "\n☠️ Target is now **Poisoned** (7 dmg/turn for 3 turns)"
            elif effect == "stun":
                target["debuffs"].append({"name": "stun", "duration": 1})
                embed.description += "\n⚡ Target is **Stunned** for 1 turn"

        elif skill_type == "buff":
            skill_stat = skill["stat"]
            skill_multiplier = skill["multiplier"]
            skill_duration = skill["duration"]


            apply_buff(user_id, skill_stat, skill_multiplier, skill_duration)
            buff_embed = discord.Embed(color=discord.Color.green(),
                                       title=f"**{interaction.user.name}** used **{skill_name}**",
                                       description=f"Gained **{skill_stat}** buff for **{skill_duration}** turns!")
            await interaction.response.send_message(embed=buff_embed)
            db.dump()
            self.view_ref.stop()

        updated_hp = target["hp"]
        hp_bar = create_hp_bar(updated_hp, max_hp)
        embed.add_field(name=f"{target['name']} HP", value=hp_bar, inline=False)
        await interaction.response.send_message(embed=embed)
        self.view_ref.stop()


class PassButton(Button):
    def __init__(self, view):
        super().__init__(label="Pass", style=discord.ButtonStyle.secondary)
        self.view_ref = view

    async def callback(self, interaction: discord.Interaction):
        if interaction.user.id != self.view_ref.player_id:
            await interaction.response.send_message("Not your turn!", ephemeral=True)
            return

        self.view_ref.chosen_skill = None
        await interaction.response.send_message("You passed your turn.")
        self.view_ref.stop()

class UseButton(Button):
    def __init__(self, view):
        super().__init__(label="Use", style=discord.ButtonStyle.green)
        self.view_ref = view

    async def callback(self, interaction: discord.Interaction):
        if interaction.user.id != self.view_ref.player_id:
            await interaction.response.send_message("Not your turn!", ephemeral=True)
            return

        user_id = str(interaction.user.id)
        inv_key = f"inventory_{user_id}"
        inventory = db.get(inv_key) or {}
        consumables_list = inventory.get("consumables", [])

        if not consumables_list:
            await interaction.response.send_message("You have no consumables!", ephemeral=True)
            return

        view = ConsumableUseView(user_id, consumables_list, self.view_ref)
        await interaction.response.send_message("🧪 Select a consumable to use:", view=view, ephemeral=True)
        await view.wait()
        self.view_ref.stop()


class ConsumableUseView(discord.ui.View):
    def __init__(self, user_id: str, consumables_list: list, parent_view):
        super().__init__(timeout=30)
        self.add_item(ConsumableSelect(user_id, consumables_list, parent_view))

class ConsumableSelect(discord.ui.Select):
    def __init__(self, user_id: str, consumables_list: list, parent_view):
        self.user_id = user_id
        self.parent_view = parent_view

        options = [
            discord.SelectOption(
                label=f"{item['name']} x{item.get('quantity', 1)}",
                description=item["data"].get("desc", "No description."),
                value=item["name"]
            )
            for item in consumables_list
        ]

        super().__init__(placeholder="Choose a consumable to use", options=options)

    async def callback(self, interaction: discord.Interaction):
        selected_item_name = self.values[0]
        inv_key = f"inventory_{self.user_id}"
        inventory = db.get(inv_key) or {}
        consumables = inventory.get("consumables", [])

        selected_entry = None
        selected_index = None
        for idx, entry in enumerate(consumables):
            if entry["name"] == selected_item_name:
                selected_entry = entry
                selected_index = idx
                break

        if not selected_entry:
            await interaction.response.send_message("Item not found.", ephemeral=True)
            return

        item_data = selected_entry["data"]
        effect = item_data.get("Effect")
        amount = item_data.get("Amount", 0)

        stats = db.dget(str(self.user_id), "stats") or {}
        updated = False

        if effect == "Heal":
            max_hp = stats.get("MaxHealth", 100)
            current_hp = stats.get("Health", 100)
            healed = int(max_hp * amount)
            stats["Health"] = min(current_hp + healed, max_hp)
            message = f"🌿 {interaction.user.name} healed **{healed} HP** using **{selected_item_name}**!"
            updated = True

        elif effect == "ManaHeal":
            max_mana = stats.get("Mana", 0)
            current_mana = stats.get("CurrentMana", max_mana)
            restored = int(max_mana * amount)
            stats["CurrentMana"] = min(current_mana + restored, max_mana)
            message = f"🔮 {interaction.user.name} restored **{restored} Mana** using **{selected_item_name}**!"
            updated = True
        else:
            message = f"{interaction.user.name} used **{selected_item_name}** but nothing happened."

        if updated:
            db.dadd(str(self.user_id), ("stats", stats))

        # Reduce or remove item
        selected_entry["quantity"] -= 1
        if selected_entry["quantity"] <= 0:
            consumables.pop(selected_index)
        else:
            consumables[selected_index] = selected_entry

        inventory["consumables"] = consumables
        db.set(inv_key, inventory)
        db.dump()

        embed = discord.Embed(color=discord.Color.green(), title=message)
        await interaction.response.send_message(embed=embed)
        self.parent_view.stop()

class TargetSelect(discord.ui.Select):
    def __init__(self, view, enemies):
        options = [
            discord.SelectOption(
                label=f"{enemy['name']} {(enemy['hp'] or enemy['base_hp'])} HP)",
                value=str(index)
            )
            for index, enemy in enumerate(enemies)
        ]
        super().__init__(placeholder="Choose your target", options=options)
        self.view_ref = view

    async def callback(self, interaction: discord.Interaction):
        if interaction.user.id != self.view_ref.player_id:
            await interaction.response.send_message("Not your turn!", ephemeral=True)
            return

        self.view_ref.selected_target = int(self.values[0])
        await interaction.response.send_message(
            f"You selected **{self.view_ref.session.enemies[self.view_ref.selected_target]['name']}**.",
            ephemeral=True
        )


