import logging
import asyncio
import os
import json
from aiogram import Bot, Dispatcher, types, F
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.filters import Command
from datetime import datetime
import gspread
from oauth2client.service_account import ServiceAccountCredentials

# Telegram токен и список админов
API_TOKEN = "8155269556:AAF1PyQHfNl77ButkzhhT0jNJRpJh5DkX0g"
ADMIN_IDS = [7561197665, 736348190]  # список ID админов

# Telegram бот
logging.basicConfig(level=logging.INFO)
bot = Bot(token=API_TOKEN)
dp = Dispatcher()

# Главное меню
main_menu = ReplyKeyboardMarkup(
    keyboard=[[KeyboardButton(text="📞 Получить консультацию")]],
    resize_keyboard=True
)

# Состояния
user_states = {}
user_questions = {}
pending_payments = {}

# Команда /start
@dp.message(Command("start"))
async def send_welcome(message: types.Message):
    await message.answer(
        "Добро пожаловать в юридический бот! Мы помогаем быстро и удобно получить профессиональную консультацию по вашему вопросу.\n\n""💰Стоимость консультации — 49 сом.\n\n""🔽Нажмите на кнопку ниже, чтобы начать.",
        reply_markup=main_menu
    )

# Получить консультацию
@dp.message(F.text == "📞 Получить консультацию")
async def start_consultation(message: types.Message):
    user_states[message.chat.id] = "waiting_for_question"
    await message.answer("✍️ Опишите ваш вопрос как можно подробнее, чтобы юрист мог быстро помочь.\n\n"
                        "🔽 Пример: \"Меня хотят уволить без причины. Что делать?\"")

# Получение вопроса
@dp.message(lambda message: user_states.get(message.chat.id) == "waiting_for_question")
async def receive_question(message: types.Message):
    chat_id = message.chat.id
    user_states[chat_id] = None
    user_questions[chat_id] = message.text

    pay_buttons = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="💳 Оплатить через M Bank", url="https://app.mbank.kg/qr/")],
        [InlineKeyboardButton(text="💳 Оплатить через O!Bank", url="https://api.dengi.o.kg/")],
        [InlineKeyboardButton(text="💳 Оплатить через Bakai Bank", url="https://bakai24.app")],
        [InlineKeyboardButton(text="✅ Я оплатил", callback_data="paid")]
    ])

    await message.answer("✅ Спасибо! Мы получили ваш вопрос:\n\n" + message.text)
    await message.answer("💰 Стоимость консультации — *49 сом*\n\n""🔐 После оплаты юрист получит ваш вопрос и ответит в кратчайшие сроки..\n\n"
    "📌 *Дополнительные реквизиты:*\n"
    "• M Банк: `+996704806488`\n"
    "• O! Банк: `+996704806488`\n\n"
    "🔽 Выберите способ оплаты ниже:", parse_mode="Markdown", reply_markup=pay_buttons)

# Нажата кнопка "Я оплатил"
@dp.callback_query(F.data == "paid")
async def handle_paid_button(call: types.CallbackQuery):
    user = call.from_user
    chat_id = call.message.chat.id
    question = user_questions.get(chat_id, "неизвестно")
    pending_payments[chat_id] = question

    await call.message.answer("Мы уведомили администратора о вашей оплате.\n\n""⏳ Пожалуйста, ожидайте подтверждение (обычно 1–5 минут).")
    await call.answer()

    for admin_id in ADMIN_IDS:
        confirm_keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [
                InlineKeyboardButton(text="✅ Подтвердить", callback_data=f"confirm_{chat_id}"),
                InlineKeyboardButton(text="❌ Отклонить", callback_data=f"reject_{chat_id}")
            ]
        ])
        await bot.send_message(
            admin_id,
            f"💸 Пользователь @{user.username or user.first_name} сообщил об оплате.\n\n📩 Вопрос:\n{question}",
            reply_markup=confirm_keyboard
        )

# Подтверждение оплаты
@dp.callback_query(lambda c: c.data.startswith("confirm_"))
async def confirm_payment(call: types.CallbackQuery):
    if call.from_user.id not in ADMIN_IDS:
        await call.answer("У вас нет прав", show_alert=True)
        return

    chat_id = int(call.data.split("_")[1])
    question = pending_payments.pop(chat_id, "неизвестно")
    user = await bot.get_chat(chat_id)

    contact_button = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📨 Написать юристу", url="https://t.me/lawbot_kg")]
    ])

    await bot.send_message(chat_id, "✅ Ваша оплата подтверждена! Юрист свяжется с вами в ближайшее время.", reply_markup=contact_button)
    await call.message.answer("☑️ Оплата подтверждена.")
    await call.answer()

# Отклонение оплаты
@dp.callback_query(lambda c: c.data.startswith("reject_"))
async def reject_payment(call: types.CallbackQuery):
    if call.from_user.id not in ADMIN_IDS:
        await call.answer("У вас нет прав", show_alert=True)
        return

    chat_id = int(call.data.split("_")[1])
    pending_payments.pop(chat_id, None)
    await bot.send_message(chat_id, "К сожалению, мы не смогли подтвердить вашу оплату. Убедитесь, что вы указали правильные реквизиты и повторите попытку.\n\n"
    "Если вы уверены, что всё оплатили — напишите нам: [@lawbot_kg](https://t.me/lawbot_kg)", parse_mode="Markdown")
    await call.message.answer("⛔ Оплата отклонена.")
    await call.answer()

# Команда /admin
@dp.message(Command("admin"))
async def admin_panel(message: types.Message):
    if message.from_user.id not in ADMIN_IDS:
        await message.answer("⛔ У вас нет доступа к админ-панели.")
        return

    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🕒 Заявки в ожидании", callback_data="view_pending")]
    ])
    await message.answer("🔧 Админ-панель:", reply_markup=keyboard)

# Просмотр заявок
@dp.callback_query(F.data == "view_pending")
async def view_pending(call: types.CallbackQuery):
    if call.from_user.id not in ADMIN_IDS:
        await call.answer("Нет доступа", show_alert=True)
        return

    if not pending_payments:
        await call.message.answer("📭 Нет заявок в ожидании.")
        return

    for chat_id, question in pending_payments.items():
        confirm_keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [
                InlineKeyboardButton(text="✅ Подтвердить", callback_data=f"confirm_{chat_id}"),
                InlineKeyboardButton(text="❌ Отклонить", callback_data=f"reject_{chat_id}")
            ]
        ])
        await call.message.answer(f"🧾 Заявка от ID {chat_id}:\n{question}", reply_markup=confirm_keyboard)

    await call.answer()

# Запуск бота
async def main():
    await dp.start_polling(bot)

if __name__ == '__main__':
    asyncio.run(main())
