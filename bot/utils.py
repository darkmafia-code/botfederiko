import datetime
from aiogram import types
from .config import SCORES, LEVELS, AFK_LEVEL, WATERMARK


def compute_total_score(stats):
    # stats is a UserChatStats object
    return stats.messages_sent * SCORES["message"] + \
        stats.replies_sent * SCORES["reply"] + \
        stats.reactions_given * SCORES["reaction_given"] + \
        stats.reactions_received * SCORES["reaction_received"] + \
        stats.deleted_messages * SCORES["deleted"]


def get_level(score: float):
    for low, high, name in LEVELS:
        if low <= score < high:
            return name
    return AFK_LEVEL[2]


def watermark(text: str) -> str:
    return f"{text}{WATERMARK}"


def today():
    return datetime.datetime.utcnow().date()


def update_streak(stats):
    today_date = today()
    if stats.last_activity_date and stats.last_activity_date.date() == today_date:
        return
    delta = (today_date - stats.last_activity_date.date()).days if stats.last_activity_date else 0
    if delta == 1:
        stats.current_streak += 1
    elif delta > 1:
        stats.current_streak = 1
    stats.last_activity_date = datetime.datetime.utcnow()
    if stats.current_streak > stats.longest_streak:
        stats.longest_streak = stats.current_streak


def parse_buttons(buttons_text: str) -> types.InlineKeyboardMarkup | None:
    """Parse buttons string into InlineKeyboardMarkup.

    Format: "Label1|https://url1;Label2|https://url2"
    If `buttons_text` is empty or 'none' -> returns None.
    """
    if not buttons_text:
        return None
    txt = buttons_text.strip()
    if txt.lower() in ("none", "no", "-"):
        return None

    buttons = []
    parts = [p.strip() for p in txt.split(";") if p.strip()]
    for part in parts:
        if "|" in part:
            label, target = [s.strip() for s in part.split("|", 1)]
            if target.startswith("http"):
                buttons.append([types.InlineKeyboardButton(text=label, url=target)])
            else:
                buttons.append([types.InlineKeyboardButton(text=label, callback_data=target)])
        else:
            # plain label
            buttons.append([types.InlineKeyboardButton(text=part, callback_data=part)])

    if not buttons:
        return None
    return types.InlineKeyboardMarkup(inline_keyboard=buttons)
