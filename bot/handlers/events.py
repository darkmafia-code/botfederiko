from aiogram import Router, types
from aiogram.types import Message
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from loguru import logger

from ..models import Chat, User, UserChatStats
from ..utils import update_streak, compute_total_score

router = Router()


@router.my_chat_member()
async def chat_member_update(update: types.ChatMemberUpdated, db: AsyncSession = None):
    logger.info(f"🔔 Chat member update in chat {update.chat.id}, new status {update.new_chat_member.status}")
    if update.new_chat_member.user.id == update.bot.id and update.new_chat_member.status in ("member", "administrator"):
        chat = await db.get(Chat, update.chat.id)
        if not chat:
            chat = Chat(id=update.chat.id, title=update.chat.title or "Unknown")
            db.add(chat)
            await db.flush()
            logger.info(f"✅ Registered chat {update.chat.id} via my_chat_member")


@router.message_reaction()
async def reaction_handler(reaction: types.MessageReaction, db: AsyncSession = None):
    logger.debug(f"Reaction {reaction.type} by {reaction.user.id} in chat {reaction.chat.id}")


@router.message(deep_link=None)
async def message_deleted(message: Message, db: AsyncSession = None):
    pass


@router.message()
async def message_handler(message: Message, db: AsyncSession):
    logger.info(f"🔴 MESSAGE HANDLER CALLED! Chat ID: {message.chat.id}, User ID: {message.from_user.id}, Type: {message.chat.type}")
    if message.from_user.is_bot:
        logger.debug(f"Skipping bot message from {message.from_user.id}")
        return

    try:
        logger.debug(f"Opened DB session for chat {message.chat.id}")
        try:
            chat = await db.get(Chat, message.chat.id)
            if not chat:
                logger.info(f"❌ Chat {message.chat.id} not found in DB, creating...")
                chat = Chat(id=message.chat.id, title=message.chat.title or "Unknown")
                db.add(chat)
                await db.flush()
                logger.info(f"✅ Chat {message.chat.id} created and flushed to DB")
            else:
                logger.debug(f"Chat {message.chat.id} already exists in DB")
        except IntegrityError as e:
            logger.warning(f"IntegrityError on chat {message.chat.id}: {e}")
            await db.rollback()
            chat = await db.get(Chat, message.chat.id)
        except Exception as e:
            logger.error(f"Unexpected error creating chat: {e}", exc_info=True)
            return

        try:
            user = await db.get(User, message.from_user.id)
            if not user:
                logger.info(f"❌ User {message.from_user.id} not found in DB, creating...")
                user = User(
                    id=message.from_user.id,
                    username=message.from_user.username,
                    first_name=message.from_user.first_name,
                    last_name=message.from_user.last_name,
                )
                db.add(user)
                await db.flush()
                logger.info(f"✅ User {message.from_user.id} created and flushed to DB")
            else:
                logger.debug(f"User {message.from_user.id} already exists in DB")
        except IntegrityError as e:
            logger.warning(f"IntegrityError on user {message.from_user.id}: {e}")
            await db.rollback()
            user = await db.get(User, message.from_user.id)
        except Exception as e:
            logger.error(f"Unexpected error creating user: {e}", exc_info=True)
            return

        try:
            await db.commit()
            logger.debug(f"Committed chat and user for {message.from_user.id}")
        except Exception as e:
            logger.error(f"Error committing chat/user: {e}")
            await db.rollback()

        try:
            stmt = select(UserChatStats).where(
                (UserChatStats.chat_id == message.chat.id) &
                (UserChatStats.user_id == message.from_user.id)
            )
            result = await db.execute(stmt)
            stats = result.scalars().first()

            if not stats:
                logger.info(f"❌ Stats not found for user {message.from_user.id} in chat {message.chat.id}, creating...")
                stats = UserChatStats(chat_id=message.chat.id, user_id=message.from_user.id)
                db.add(stats)
                await db.flush()
                logger.info(f"✅ Stats created and flushed for user {message.from_user.id}")
            else:
                logger.debug(f"Stats found for user {message.from_user.id} in chat {message.chat.id}")
        except Exception as e:
            logger.error(f"Error getting/creating stats: {e}", exc_info=True)
            return

        if stats.messages_sent is None:
            stats.messages_sent = 0
        if stats.replies_sent is None:
            stats.replies_sent = 0
        if stats.reactions_given is None:
            stats.reactions_given = 0.0
        if stats.reactions_received is None:
            stats.reactions_received = 0.0

        stats.messages_sent += 1
        logger.debug(f"Incremented messages_sent to {stats.messages_sent}")

        if message.reply_to_message:
            stats.replies_sent += 1
            logger.debug(f"Message is a reply, incremented replies_sent to {stats.replies_sent}")

        try:
            update_streak(stats)
            stats.total_score = compute_total_score(stats)
            logger.debug(f"Updated streak and computed score: {stats.total_score}")
        except Exception as e:
            logger.error(f"Error updating streak/score: {e}", exc_info=True)

        try:
            await db.commit()
            logger.info(f"✅ FINAL COMMIT SUCCESS: User {message.from_user.id} in chat {message.chat.id} | msgs={stats.messages_sent}, replies={stats.replies_sent}, score={stats.total_score}")
        except Exception as e:
            logger.error(f"Error on final commit: {e}", exc_info=True)
            await db.rollback()

    except Exception as e:
        logger.error(f"❌ FATAL ERROR in message_handler: {e}", exc_info=True)