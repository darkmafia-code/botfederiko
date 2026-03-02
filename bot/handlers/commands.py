from aiogram import Router, types
from aiogram.filters import Command
from sqlalchemy import select
from loguru import logger

from ..config import WATERMARK
from ..database import SessionLocal
from ..utils import compute_total_score, get_level, watermark
from ..models import UserChatStats, User, Chat

router = Router()


async def get_or_create_stats(db, chat_id, user_id):
    """Get or create user stats for a chat."""
    stmt = select(UserChatStats).where(
        (UserChatStats.chat_id == chat_id) & (UserChatStats.user_id == user_id)
    )
    result = await db.execute(stmt)
    stats = result.scalars().first()
    
    if not stats:
        stats = UserChatStats(chat_id=chat_id, user_id=user_id)
        db.add(stats)
        await db.commit()
        await db.refresh(stats)
    
    return stats


@router.message(Command("start"))
async def start_cmd(message: types.Message):
    """Handle /start command."""
    text = "👋 Привет! Я бот геймификации чата.\nНапиши /help для справки."
    await message.answer(watermark(text))


@router.message(Command("help"))
@router.message(Command("hl"))
async def help_cmd(message: types.Message):
    """Show help/info."""
    text = (
        "🛠 <b>Команды бота:</b>\n"
        "/me - Мои очки и уровень\n"
        "/rank - Рейтинг в чате\n"
        "/top - Топ участников\n"
        "/achievements - Мои достижения\n"
        "/streak - Мой текущий стрик\n"
        "/compare @user - Сравнить с пользователем"
    )
    await message.answer(watermark(text))


@router.message(Command("me"))
async def me_cmd(message: types.Message, db: AsyncSession):
    """Show user's stats."""
    try:
        stats = await get_or_create_stats(db, message.chat.id, message.from_user.id)
        score = compute_total_score(stats) if stats else 0
        level = get_level(score)
        
        user_name = message.from_user.full_name or f"User {message.from_user.id}"
        
        # Ensure all values are valid
        msgs = stats.messages_sent or 0
        replies = stats.replies_sent or 0
        current = stats.current_streak or 0
        longest = stats.longest_streak or 0
        
        text = (
            f"👤 <b>{user_name}</b>\n"
            f"💯 Очки: {score:.1f}\n"
            f"📊 Уровень: {level}\n"
            f"🔥 Стрик: {current} (макс {longest})\n"
            f"📝 Сообщений: {msgs}\n"
            f"↩️ Ответов: {replies}"
        )
        await message.answer(watermark(text))
    except Exception as e:
        logger.error(f"Error in /me: {e}")
        await message.answer("❌ Ошибка при получении данных")


@router.message(Command("rank"))
async def rank_cmd(message: types.Message, db: AsyncSession):
    """Show rating in chat."""
    try:
        stmt = select(UserChatStats).where(UserChatStats.chat_id == message.chat.id)
        result = await db.execute(stmt)
        stats_list = result.scalars().all()
        
        if not stats_list:
            await message.answer("📊 Рейтинг пока пуст")
            return
        
        ranked = sorted(stats_list, key=lambda s: compute_total_score(s), reverse=True)
        text = "🏅 <b>Рейтинг в чате (топ-10):</b>\n"
        
        for idx, s in enumerate(ranked[:10], start=1):
            user = await db.get(User, s.user_id)
            if user:
                user_name = user.username or f"User {user.id}"
                score = compute_total_score(s)
                text += f"{idx}. @{user_name} - {score:.1f} очков\n"
        
        await message.answer(watermark(text))
    except Exception as e:
        logger.error(f"Error in /rank: {e}")
        await message.answer("❌ Ошибка при получении рейтинга")


@router.message(Command("top"))
async def top_cmd(message: types.Message):
    """Show top users."""
    await message.answer("🔄 Функция в разработке")


@router.message(Command("achievements"))
async def achievements_cmd(message: types.Message):
    """Show achievements."""
    await message.answer("🎖️ Ваши достижения: пока нет")


@router.message(Command("streak"))
async def streak_cmd(message: types.Message, db: AsyncSession):
    """Show streak."""
    try:
        stats = await get_or_create_stats(db, message.chat.id, message.from_user.id)
        text = f"🔥 Текущий стрик: {stats.current_streak}\n⭐ Максимальный: {stats.longest_streak}"
        await message.answer(watermark(text))
    except Exception as e:
        logger.error(f"Error in /streak: {e}")
        await message.answer("❌ Ошибка")


@router.message(Command("compare"))
async def compare_cmd(message: types.Message, db: AsyncSession):
    """Compare with another user."""
    # aiogram v3: Message has no get_args(); parse from text safely
    text = message.text or ""
    parts = text.split(maxsplit=1)
    if len(parts) <= 1:
        await message.answer("❌ Укажите пользователя: /compare @username")
        return
    args = parts[1].split()
    if not args:
        await message.answer("❌ Укажите пользователя: /compare @username")
        return
    username = args[0].lstrip("@")
    
    try:
        stmt = select(User).where(User.username == username)
        result = await db.execute(stmt)
        other = result.scalars().first()
        
        if not other:
            await message.answer(f"❌ Пользователь @{username} не найден")
            return
        
        stats1 = await get_or_create_stats(db, message.chat.id, message.from_user.id)
        stats2 = await get_or_create_stats(db, message.chat.id, other.id)
        
        score1 = compute_total_score(stats1)
        score2 = compute_total_score(stats2)
        
        text = (
            f"⚔️ <b>Сравнение</b>\n"
            f"👤 Вы: {score1:.1f}\n"
            f"👤 @{username}: {score2:.1f}\n"
            f"{'🏆 Вы впереди!' if score1 > score2 else '📉 Отстаёте' if score1 < score2 else '⚖️ Равно'}"
        )
        await message.answer(watermark(text))
    except Exception as e:
        logger.error(f"Error in /compare: {e}")
        await message.answer("❌ Ошибка при сравнении")
