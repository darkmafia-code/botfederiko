import os
from dotenv import load_dotenv

load_dotenv()

BOT_TOKEN: str = os.getenv("BOT_TOKEN")
ADMIN_ID: int = int(os.getenv("ADMIN_ID", "0"))

if not BOT_TOKEN or BOT_TOKEN == "your_bot_token_here":
    raise ValueError(
        "❌ BOT_TOKEN is not set in .env file!\n"
        "Please create a .env file or edit the existing one with your actual Telegram bot token.\n"
        "Copy .env.example to .env and replace 'your_bot_token_here' with your real token."
    )

# watermark appended to every bot message
WATERMARK = "\n\n———\nСоздано группой @xv_group | Автор @XP_V1ruS"

# scoring constants
SCORES = {
    "message": 1,
    "reply": 2,
    "reaction_given": 0.5,
    "reaction_received": 1,
    "deleted": -3,
    "day_missing": -2,
}

# levels thresholds
LEVELS = [
    (0, 50, "🥉 Новичок"),
    (50, 150, "🥈 Активист"),
    (150, 300, "🥇 Завсегдатай"),
    (300, float("inf"), "🏆 Легенда чата"),
]
AFK_LEVEL = (-float("inf"), -10, "☠️ AFK")
