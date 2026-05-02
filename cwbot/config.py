import os
from dotenv import load_dotenv
load_dotenv()

DISCORD_TOKEN   = os.getenv("DISCORD_TOKEN", "")
PREFIX          = os.getenv("PREFIX", "!")

# BIG Games PS99 API
API_BASE        = "https://ps99.biggamesapi.io/api"
IMAGE_BASE      = "https://ps99.biggamesapi.io/image"

# Roblox APIs
ROBLOX_USERS    = "https://users.roblox.com/v1/usernames/users"
ROBLOX_USER_URL = "https://users.roblox.com/v1/users/{uid}"

# Polling interval in seconds (API caches 60 s → poll every 90 s)
POLL_INTERVAL   = 90

# Max snapshots stored per clan (168 = 7 days at 1/hour)
MAX_SNAPSHOTS   = 168

# Rank search depth (how many leaderboard pages to scan)
RANK_SEARCH_PAGES = 100

# GitHub Gist backup (optional)
GIST_ID         = os.getenv("GITHUB_GIST_ID", "")
GITHUB_TOKEN    = os.getenv("GITHUB_TOKEN", "")

# Keep-alive for Render.com
RENDER_URL      = os.getenv("RENDER_URL", "")
KEEP_ALIVE_PORT = int(os.getenv("PORT", "3000"))
