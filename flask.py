from flask import Flask, jsonify
import threading

app = Flask(__name__)
from db import db

@app.route('/api/players', methods=['GET'])
def get_players():
    players = []
    # Get all user IDs from your database
    for user_id in db.getall():
        if not user_id.startswith('inventory_') and not user_id.startswith('gold_'):
            player_data = {
                'id': user_id,
                'username': 'Unknown',  # You'll need to fetch from Discord API
                'level': db.dget(user_id, 'level'),
                'xp': db.dget(user_id, 'xp'),
                'gold': db.get(f'gold_{user_id}'),
                'class': db.dget(user_id, 'class'),
                'subclass': db.dget(user_id, 'subclass'),
                'awakening': db.dget(user_id, 'awakening'),
                'equipped_weapon': db.dget(user_id, 'equipped_weapon'),
                'stats': db.dget(user_id, 'stats')
            }
            players.append(player_data)
    return jsonify(players)

@app.route('/api/player/<user_id>', methods=['GET'])
def get_player(user_id):
    # Return specific player data
    pass

# Run Flask in a separate thread
def run_api():
    app.run(host='0.0.0.0', port=5000)

# In your bot's main code:
api_thread = threading.Thread(target=run_api)
api_thread.daemon = True
api_thread.start()
