from apscheduler.schedulers.asyncio import AsyncIOScheduler
from .utils import watermark
from .database import SessionLocal
from .models import Chat, UserChatStats
from sqlalchemy import select
import datetime

scheduler = AsyncIOScheduler(timezone="Europe/Moscow")


async def weekly_summary():
    async with SessionLocal() as db:
        result = await db.execute(select(Chat))
        chats = result.scalars().all()
    for chat in chats:
        summary = "🏆 Итоги недели\n..."
        from aiogram import Bot
        from .config import BOT_TOKEN
        bot = Bot(token=BOT_TOKEN)
        await bot.send_message(chat.id, watermark(summary))


def start_scheduler():
    scheduler.add_job(weekly_summary, "cron", day_of_week="sun", hour=21, minute=0)
    scheduler.start()
