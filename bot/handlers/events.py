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
    """Register chat when bot added or settings changed."""
    logger.info(f"🔔 Chat member update in chat {update.chat.id}, new status {update.new_chat_member.status}")
    if update.new_chat_member.user.id == update.bot.id and update.new_chat_member.status in ("member", "administrator"):
        # bot added to chat, ensure chat record
        chat = await db.get(Chat, update.chat.id)
        if not chat:
            chat = Chat(id=update.chat.id, title=update.chat.title or "Unknown")
            db.add(chat)
            await db.flush()
            logger.info(f"✅ Registered chat {update.chat.id} via my_chat_member")


@router.message_reaction()
async def reaction_handler(reaction: types.MessageReaction, db: AsyncSession = None):
    logger.debug(f"Reaction {reaction.type} by {reaction.user.id} in chat {reaction.chat.id}")
    # optional: increment stats


@router.message(deep_link=None)
async def message_deleted(message: Message, db: AsyncSession = None):
    # message deletion events aren't supported directly; listen to service messages? or use other update types
    pass


@router.message()
async def message_handler(message: Message, db: AsyncSession):
    """Track message events."""
    # Log incoming message
    logger.debug(f"📩 Message received from {message.from_user.id} in chat {message.chat.id}: {message.text[:50] if message.text else 'no text'}")
    
    if message.from_user.is_bot:
        logger.debug(f"Skipping bot message from {message.from_user.id}")
        return
    
    try:
        async with SessionLocal() as db:
            # Get or create chat
            try:
                chat = await db.get(Chat, message.chat.id)
                if not chat:
                    logger.debug(f"Creating new chat {message.chat.id} with title: {message.chat.title}")
                    chat = Chat(id=message.chat.id, title=message.chat.title or "Unknown")
                    db.add(chat)
                    await db.flush()
                    logger.debug(f"Chat {message.chat.id} created and flushed")
            except IntegrityError as e:
                logger.warning(f"IntegrityError creating chat {message.chat.id}: {e}")
                await db.rollback()
                chat = await db.get(Chat, message.chat.id)
            
            # Get or create user
            try:
                user = await db.get(User, message.from_user.id)
                if not user:
                    logger.debug(f"Creating new user {message.from_user.id}")
                    user = User(
                        id=message.from_user.id,
                        username=message.from_user.username,
                        first_name=message.from_user.first_name,
                        last_name=message.from_user.last_name,
                    )
                    db.add(user)
                    await db.flush()
                    logger.debug(f"User {message.from_user.id} created and flushed")
            except IntegrityError as e:
                logger.warning(f"IntegrityError creating user {message.from_user.id}: {e}")
                await db.rollback()
                user = await db.get(User, message.from_user.id)
            
            await db.commit()
            logger.debug(f"Chat and user committed for {message.from_user.id}")
            
            # Get or create stats
            stmt = select(UserChatStats).where(
                (UserChatStats.chat_id == message.chat.id) &
                (UserChatStats.user_id == message.from_user.id)
            )
            result = await db.execute(stmt)
            stats = result.scalars().first()
            
            if not stats:
                logger.debug(f"Creating new stats for user {message.from_user.id} in chat {message.chat.id}")
                stats = UserChatStats(chat_id=message.chat.id, user_id=message.from_user.id)
                db.add(stats)
                await db.flush()
                logger.debug(f"Stats created and flushed for user {message.from_user.id}")
            
            # Ensure all fields are not None (safety check)
            if stats.messages_sent is None:
                stats.messages_sent = 0
            if stats.replies_sent is None:
                stats.replies_sent = 0
            if stats.reactions_given is None:
                stats.reactions_given = 0.0
            if stats.reactions_received is None:
                stats.reactions_received = 0.0
            
            # Update stats
            stats.messages_sent += 1
            logger.debug(f"Incremented messages_sent to {stats.messages_sent} for user {message.from_user.id}")
            
            if message.reply_to_message:
                stats.replies_sent += 1
                logger.debug(f"Incremented replies_sent to {stats.replies_sent} for user {message.from_user.id}")
            
            update_streak(stats)
            stats.total_score = compute_total_score(stats)
            logger.debug(f"Updated streak and score for user {message.from_user.id}, total_score={stats.total_score}")
            
            await db.commit()
            logger.info(f"✅ Tracked message from {user.id} in chat {message.chat.id} (msgs={stats.messages_sent})")
            
    except Exception as e:
        logger.error(f"❌ Error tracking message: {e}", exc_info=True)

