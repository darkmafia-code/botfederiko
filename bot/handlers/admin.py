from aiogram import Router, types, F
from aiogram.filters import Command
from sqlalchemy import select
from loguru import logger
import asyncio

from ..config import ADMIN_ID, WATERMARK
from ..database import SessionLocal
from ..models import Chat
from ..utils import watermark, parse_buttons

router = Router()


# Per-admin in-memory broadcast state
# structure: {admin_id: {stage: 'await_content'|'await_buttons'|'preview', content: {...}, markup: InlineKeyboardMarkup}}
broadcast_state: dict[int, dict] = {}


@router.message(Command("broadcast"))
async def broadcast_cmd(message: types.Message):
    """Admin broadcast command."""
    if message.from_user.id != ADMIN_ID:
        logger.warning(f"Non-admin {message.from_user.id} tried /broadcast")
        return

    admin_id = message.from_user.id
    logger.debug(f"/broadcast invoked by admin {admin_id}")
    broadcast_state[admin_id] = {"stage": "await_content"}
    await message.reply(
        "📨 Отправьте сообщение для рассылки. Можно прислать фото (с подписью) или обычный текст."
    )


@router.message(Command("stats"))
async def stats_cmd(message: types.Message):
    """Show bot stats (admin only)."""
    if message.from_user.id != ADMIN_ID:
        return

    try:
        async with SessionLocal() as db:
            result = await db.execute(select(Chat))
            chats = result.scalars().all()
            await message.answer(f"📊 Чатов в базе: {len(chats)}")
    except Exception as e:
        logger.error(f"Error getting stats: {e}")


@router.message()
async def admin_broadcast_flow(message: types.Message):
    """Handle admin messages during broadcast flow (content -> buttons -> preview)."""
    admin_id = message.from_user.id
    if admin_id != ADMIN_ID:
        return

    state = broadcast_state.get(admin_id)
    if not state:
        return

    stage = state.get("stage")
    logger.debug(f"admin_broadcast_flow stage={stage} for admin={admin_id}")

    # Ignore all messages when waiting for callback confirmation
    if stage == "preview":
        await message.reply("⏳ Ожидаю вашего выбора: подтвердить или отменить рассылку")
        return

    if stage == "await_content":
        # Capture photo or text
        if message.photo:
            photo = message.photo[-1]
            file_id = photo.file_id
            caption = message.caption or ""
            logger.debug(f"Captured photo for broadcast by {admin_id}, file_id={file_id}")
            state["content"] = {"type": "photo", "file_id": file_id, "text": caption}
        else:
            # treat text as caption for message-only broadcast
            text = message.text or ""
            logger.debug(f"Captured text for broadcast by {admin_id}: {text[:80]}")
            state["content"] = {"type": "text", "text": text}

        state["stage"] = "await_buttons"
        await message.reply(
            "📎 Теперь введите кнопки в формате: Label1|https://url1;Label2|https://url2\n"
            "Если кнопок нет — отправьте 'none'."
        )
        return

    if stage == "await_buttons":
        buttons_text = (message.text or "").strip()
        logger.debug(f"Buttons text from admin {admin_id}: {buttons_text}")
        markup = parse_buttons(buttons_text)
        state["markup"] = markup

        # send preview to admin
        content = state.get("content", {})
        preview = None
        try:
            if content.get("type") == "photo":
                preview = await message.bot.send_photo(
                    chat_id=admin_id,
                    photo=content.get("file_id"),
                    caption=watermark(content.get("text", "")),
                    reply_markup=markup,
                )
            else:
                preview = await message.bot.send_message(
                    chat_id=admin_id,
                    text=watermark(content.get("text", "")),
                    reply_markup=markup,
                )
        except Exception as e:
            logger.error(f"Error sending preview: {e}")
            await message.reply("❌ Не удалось отправить предпросмотр.")
            broadcast_state.pop(admin_id, None)
            return

        state["stage"] = "preview"
        state["preview_message_id"] = getattr(preview, "message_id", None)

        # ask for confirmation via inline buttons
        confirm_buttons = [
            [
                types.InlineKeyboardButton(text="✅ Подтвердить", callback_data="broadcast:confirm"),
                types.InlineKeyboardButton(text="❌ Отменить", callback_data="broadcast:cancel"),
            ]
        ]
        kb = types.InlineKeyboardMarkup(inline_keyboard=confirm_buttons)
        try:
            await message.bot.send_message(admin_id, "❗️ Предпросмотр. Подтвердите рассылку:", reply_markup=kb)
            logger.debug(f"Sent confirmation buttons to admin {admin_id}")
        except Exception as e:
            logger.error(f"Error sending confirmation message: {e}")
            broadcast_state.pop(admin_id, None)
        return


@router.callback_query(F.data.startswith("broadcast:"))
async def broadcast_confirm_cb(query: types.CallbackQuery):
    """Handle confirm/cancel callbacks for broadcast."""
    admin_id = query.from_user.id
    if admin_id != ADMIN_ID:
        await query.answer("Только админ может управлять рассылкой", show_alert=True)
        return

    data = query.data or ""
    state = broadcast_state.get(admin_id)
    if not state:
        await query.answer("Нет активной рассылки", show_alert=True)
        return

    if data == "broadcast:cancel":
        broadcast_state.pop(admin_id, None)
        await query.message.edit_text("❌ Рассылка отменена")
        await query.answer()
        return

    if data == "broadcast:confirm":
        await query.answer("Запускаю рассылку...")
        logger.debug(f"Admin {admin_id} confirmed broadcast; starting send to chats")
        content = state.get("content", {})
        markup = state.get("markup")

        sent = 0
        failed = 0
        try:
            async with SessionLocal() as db:
                result = await db.execute(select(Chat))
                chats = result.scalars().all()
                for ch in chats:
                    try:
                        if content.get("type") == "photo":
                            await query.bot.send_photo(
                                chat_id=ch.id,
                                photo=content.get("file_id"),
                                caption=watermark(content.get("text", "")),
                                reply_markup=markup,
                            )
                        else:
                            await query.bot.send_message(
                                chat_id=ch.id,
                                text=watermark(content.get("text", "")),
                                reply_markup=markup,
                            )
                        sent += 1
                        # small throttle to avoid flooding
                        await asyncio.sleep(0.12)
                    except Exception as e:
                        logger.error(f"Failed to send to {ch.id}: {e}")
                        failed += 1
        except Exception as e:
            logger.error(f"Error during broadcast: {e}")

        broadcast_state.pop(admin_id, None)
        logger.debug(f"Broadcast finished: sent={sent} failed={failed}")
        await query.message.edit_text(f"✅ Рассылка завершена. Отправлено: {sent}. Ошибок: {failed}")
        return
