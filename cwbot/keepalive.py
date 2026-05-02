"""keepalive.py – minimaler Flask-Server damit Render den Prozess nicht tötet."""
from flask import Flask
from threading import Thread
from config import KEEP_ALIVE_PORT

app = Flask(__name__)

@app.route("/")
def home():
    return "🐾 PS99 ClanWar Bot is running!"

@app.route("/ping")
def ping():
    return {"status": "ok"}

def run():
    app.run(host="0.0.0.0", port=KEEP_ALIVE_PORT, use_reloader=False)

def keep_alive():
    t = Thread(target=run, daemon=True)
    t.start()
    print(f"✅ Keep-alive Server läuft auf Port {KEEP_ALIVE_PORT}")
