import discord
from discord.ext import commands
from discord import app_commands
import sys
import os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from items import weapon, consumables  # Assuming you store weapons/consumables here
from db import db

# Initialize the Discord client
intents = discord.Intents.default()
intents.members = True
intents.message_content = True
client = commands.Bot(command_prefix=',', intents=intents)


@client.tree.command(name="shop")
async def shop(interaction: discord.Interaction):
    user_id = str(interaction.user.id)
    # setup_user(user_id)

    user_class = db.dget(user_id, "class")

    embed = discord.Embed(title=f"{user_class.title()} Shop", description= "Select a category to view details.")
    await interaction.channel.send(embed=embed, view=ShopView(user_class))

class ShopView(discord.ui.View):
    def __init__(self, user_class: str):
        super().__init__()
        self.user_class = user_class
        self.selected_category = "weapon"
        self.selected_item = None

        self.category_select = CategorySelect(self)
        self.item_select = ItemSelect(user_class, self.selected_category, self)
        self.buy_button = BuyButton()

        self.add_item(self.category_select)
        self.add_item(self.item_select)
        self.add_item(self.buy_button)

    async def update_item_dropdown(self, interaction):
        self.remove_item(self.item_select)
        self.item_select = ItemSelect(self.user_class, self.selected_category, self)
        self.add_item(self.item_select)
        await interaction.response.edit_message(view=self)

    async def show_item_detail(self, interaction):
        item_name = self.selected_item

        if self.selected_category == "consumables":
            # Consumables don't need class filtering
            item = consumables[item_name]
        else:
            # For weapons, use class filtering
            data_source = {"weapon": weapon}.get(self.selected_category, {})
            item = data_source[self.user_class][item_name]

        embed = discord.Embed(title=item_name, description=item["desc"], color=discord.Color.blue())
        embed.add_field(name="Rarity", value=item["Rarity"])
        if "Damage" in item: embed.add_field(name="Damage", value=item["Damage"])
        if "Effect" in item: embed.add_field(name="Effect", value=item["Effect"] or "None")
        embed.add_field(name="Cost", value=item["Cost"] or "Free")

        await interaction.response.edit_message(embed=embed, view=self)


class CategorySelect(discord.ui.Select):
    def __init__(self, shop_view: 'ShopView'):
        options = [
            discord.SelectOption(label="Weapons", value="weapon"),
            discord.SelectOption(label="Consumables", value="consumables")
            # Add more categories here
        ]
        super().__init__(placeholder="Select item category", options=options)
        self.shop_view = shop_view

    async def callback(self, interaction: discord.Interaction):
        self.view.selected_category = self.values[0]
        await self.view.update_item_dropdown(interaction)

class ItemSelect(discord.ui.Select):
    def __init__(self, user_class: str, category: str, shop_view: 'ShopView'):
        self.shop_view = shop_view
        self.user_class = user_class
        self.category = category

        # Handle consumables differently - no class restriction
        if category == "consumables":
            # Consumables are available to all classes
            options = [
                discord.SelectOption(label=item, description=data['desc'], value=item)
                for item, data in consumables.items()
            ]
        else:
            # For weapons, keep class restriction
            data_source = {"weapon": weapon}.get(category, {})
            class_items = data_source.get(user_class, {})
            options = [
                discord.SelectOption(label=item, description=data['desc'], value=item)
                for item, data in class_items.items()
            ]

        super().__init__(placeholder=f"Select {category}", options=options)

    async def callback(self, interaction: discord.Interaction):
        self.view.selected_item = self.values[0]
        await self.view.show_item_detail(interaction)

def migrate_inventory_format(user_id: str):
    inv_key = f"inventory_{user_id}"
    inventory = db.get(inv_key) or {}

    updated = False

    for category in list(inventory.keys()):
        category_items = inventory[category]

        # Check if it's a list of strings (old format)
        if isinstance(category_items, list) and category_items and isinstance(category_items[0], str):
            new_items = []
            for item_name in category_items:
                # Determine the source of item data
                if category == "consumables":
                    item_data = consumables.get(item_name, {})
                elif category == "weapon":
                    user_class = db.dget(user_id, "class") or "warrior"
                    item_data = weapon.get(user_class, {}).get(item_name, {})
                else:
                    item_data = {}

                new_items.append({
                    "name": item_name,
                    "data": item_data,
                    "quantity": 1
                })
            inventory[category] = new_items
            updated = True

    if updated:
        db.set(inv_key, inventory)
        db.dump()
        print(f"[Inventory Migration] Updated inventory format for user {user_id}")


class BuyButton(discord.ui.Button):
    def __init__(self):
        super().__init__(label="Buy", style=discord.ButtonStyle.green)

    async def callback(self, interaction: discord.Interaction):
        view: ShopView = self.view
        user_id = str(interaction.user.id)
        category = view.selected_category
        user_class = view.user_class
        item_name = view.selected_item

        if not item_name:
            await interaction.response.send_message("Select an item first!", ephemeral=True)
            return

        # Get item data
        if category == "consumables":
            item = consumables[item_name]
        else:
            data_source = {"weapon": weapon}.get(category, {})
            item = data_source[user_class][item_name]

        cost = item.get("Cost", 0)
        gold = db.get(f"gold_{user_id}")

        if cost is not None and gold < cost:
            await interaction.response.send_message("Not enough gold.", ephemeral=True)
            return

        # Migrate old inventory formats (only once per user)
        migrate_inventory_format(user_id)
        inv_key = f"inventory_{user_id}"
        inventory = db.get(inv_key) or {}

        # Get current list of items in that category
        category_items = inventory.get(category, [])
        item_data = dict(item)

        print(category_items)

        # Check if item already exists, and update quantity
        found = False
        for entry in category_items:
            if entry["name"] == item_name:
                entry["quantity"] += 1
                found = True
                break

        if not found:
            # Add new item with quantity = 1
            new_entry = {
                "name": item_name,
                "data": item_data,
                "quantity": 1
            }
            category_items.append(new_entry)

        inventory[category] = category_items
        success = db.set(inv_key, inventory)
        print("Set success:", success)

        db.dump()

        # Deduct gold
        if cost:
            db.set(f"gold_{user_id}", gold - cost)

        print("Stored inventory in DB:", db.get(inv_key))

        await interaction.response.send_message(
            f"<a:save3d:1385556752489119825> You bought **{item_name}**!",
            ephemeral=False
        )

