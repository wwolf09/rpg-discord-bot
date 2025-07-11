import pickledb

db = pickledb.load("data", auto_dump=False)

def get_inventory(user_id: str) -> dict:
    inv_key = f"inventory_{user_id}"
    return db.get(inv_key) or {}

def save_inventory(user_id: str, inventory: dict):
    inv_key = f"inventory_{user_id}"
    db.set(inv_key, inventory)
    db.dump()  # persist

def add_to_inventory(user_id: str, category: str, item_name: str, item_data: dict, amount: int = 1):
    inventory = get_inventory(user_id)
    category_items = inventory.get(category, [])

    for entry in category_items:
        if entry["name"] == item_name:
            entry["quantity"] += amount
            break
    else:
        category_items.append({
            "name": item_name,
            "data": item_data,
            "quantity": amount
        })

    inventory[category] = category_items
    save_inventory(user_id, inventory)

