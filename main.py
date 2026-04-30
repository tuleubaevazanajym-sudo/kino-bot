import asyncio
import logging
import aiosqlite
from flask import Flask
from threading import Thread
from aiogram import Bot, Dispatcher, types, F
from aiogram.types import Message, ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.filters import CommandStart
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode, ChatMemberStatus
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup

# --- WEB SERVER (RENDER UCHUN) ---
app = Flask('')
@app.route('/')
def home(): return "Bot is running!"
def run(): app.run(host='0.0.0.0', port=8080)
def keep_alive():
    t = Thread(target=run)
    t.start()

# --- SOZLAMALAR ---
API_TOKEN = "8719148642:AAFf7oDnYnsV2P6d97TbNIgZlpueBY0Nr6Q"
ADMIN_ID = 8475619369 
CHANNELS = ["@kinotopuzchenel/"] # Kanal oxiriga / qo'shildi

bot = Bot(token=API_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
dp = Dispatcher()

# --- HOLATLAR ---
class AddMovie(StatesGroup):
    waiting_for_video = State()
    waiting_for_caption = State()
    waiting_for_code = State()

class DeleteMovie(StatesGroup):
    waiting_for_code = State()

class Broadcast(StatesGroup):
    waiting_for_message = State()

# --- MENYULAR ---
admin_menu = ReplyKeyboardMarkup(keyboard=[
    [KeyboardButton(text="🎬 Kino qo'shish"), KeyboardButton(text="🗑 Kinoni o'chirish")],
    [KeyboardButton(text="📊 Statistika"), KeyboardButton(text="📢 Reklama")]
], resize_keyboard=True)
cancel_menu = ReplyKeyboardMarkup(keyboard=[[KeyboardButton(text="❌ Bekor qilish")]], resize_keyboard=True)

# --- FUNKSIYALAR ---
async def check_sub(user_id):
    for channel in CHANNELS:
        try:
            # Username'dan @ belgisini va / belgisini olib tashlash
            clean_channel = channel.replace("@", "").replace("/", "")
            member = await bot.get_chat_member(chat_id=f"@{clean_channel}", user_id=user_id)
            if member.status in [ChatMemberStatus.LEFT, ChatMemberStatus.KICKED]: return False
        except: continue
    return True

async def init_db():
    async with aiosqlite.connect("kino.db") as db:
        await db.execute("CREATE TABLE IF NOT EXISTS movies (code TEXT PRIMARY KEY, caption TEXT, file_id TEXT)")
        await db.execute("CREATE TABLE IF NOT EXISTS users (user_id INTEGER PRIMARY KEY)")
        await db.commit()

# --- HANDLERLAR ---
@dp.message(CommandStart())
async def start_handler(message: Message):
    async with aiosqlite.connect("kino.db") as db:
        await db.execute("INSERT OR IGNORE INTO users VALUES (?)", (message.from_user.id,))
        await db.commit()
    if message.from_user.id == ADMIN_ID:
        await message.answer("Admin xush kelibsiz!", reply_markup=admin_menu)
    else:
        await message.answer("Assalomu alaykum! Kino kodini yuboring.")

@dp.message(F.text == "❌ Bekor qilish")
async def cancel(message: Message, state: FSMContext):
    await state.clear()
    await message.answer("Amal bekor qilindi.", reply_markup=admin_menu if message.from_user.id == ADMIN_ID else None)

# --- KINO O'CHIRISH (FAQAT ADMIN UCHUN) ---
@dp.message(F.text == "🗑 Kinoni o'chirish")
async def delete_movie_start(message: Message, state: FSMContext):
    if message.from_user.id == ADMIN_ID:
        await state.set_state(DeleteMovie.waiting_for_code)
        await message.answer("O'chiriladigan kino kodini yuboring:", reply_markup=cancel_menu)

@dp.message(DeleteMovie.waiting_for_code)
async def process_delete(message: Message, state: FSMContext):
    code = message.text.strip()
    async with aiosqlite.connect("kino.db") as db:
        cursor = await db.execute("SELECT code FROM movies WHERE code = ?", (code,))
        movie = await cursor.fetchone()
        if movie:
            await db.execute("DELETE FROM movies WHERE code = ?", (code,))
            await db.commit()
            await message.answer(f"✅ Kod {code} bo'lgan kino o'chirildi!", reply_markup=admin_menu)
        else:
            await message.answer("❌ Bunday kodli kino topilmadi. Qayta urinib ko'ring:", reply_markup=cancel_menu)
    await state.clear()

# --- STATISTIKA ---
@dp.message(F.text == "📊 Statistika")
async def stats(message: Message):
    if message.from_user.id == ADMIN_ID:
        async with aiosqlite.connect("kino.db") as db:
            async with db.execute("SELECT COUNT(*) FROM users") as c1, db.execute("SELECT COUNT(*) FROM movies") as c2:
                u = (await c1.fetchone())[0]
                m = (await c2.fetchone())[0]
        await message.answer(f"📊 <b>Statistika:</b>\n\n👤 Foydalanuvchilar: {u}\n🎬 Kinolar: {m}")

# --- REKLAMA ---
@dp.message(F.text == "📢 Reklama")
async def broadcast_start(message: Message, state: FSMContext):
    if message.from_user.id == ADMIN_ID:
        await state.set_state(Broadcast.waiting_for_message)
        await message.answer("Reklama xabarini yuboring (rasm, video yoki matn):", reply_markup=cancel_menu)

@dp.message(Broadcast.waiting_for_message)
async def broadcast_send(message: Message, state: FSMContext):
    async with aiosqlite.connect("kino.db") as db:
        async with db.execute("SELECT user_id FROM users") as cursor:
            users = await cursor.fetchall()
    count = 0
    for user in users:
        try:
            await bot.copy_message(user[0], message.chat.id, message.message_id)
            count += 1
            await asyncio.sleep(0.05)
        except: continue
    await state.clear()
    await message.answer(f"✅ Reklama {count} kishiga yuborildi!", reply_markup=admin_menu)

# --- KINO QO'SHISH ---
@dp.message(F.text == "🎬 Kino qo'shish")
async def start_add(message: Message, state: FSMContext):
    if message.from_user.id == ADMIN_ID:
        await state.set_state(AddMovie.waiting_for_video)
        await message.answer("Kinoni yuboring (video formatida):", reply_markup=cancel_menu)

@dp.message(AddMovie.waiting_for_video, F.video)
async def process_video(message: Message, state: FSMContext):
    await state.update_data(file_id=message.video.file_id)
    await state.set_state(AddMovie.waiting_for_caption)
    await message.answer("Kino haqida ma'lumot yuboring:")

@dp.message(AddMovie.waiting_for_caption, F.text)
async def process_caption(message: Message, state: FSMContext):
    await state.update_data(caption=message.text)
    await state.set_state(AddMovie.waiting_for_code)
    await message.answer("Kino uchun kod yuboring:")

@dp.message(AddMovie.waiting_for_code, F.text)
async def process_code(message: Message, state: FSMContext):
    data = await state.get_data()
    code = message.text.strip()
    async with aiosqlite.connect("kino.db") as db:
        await db.execute("INSERT OR REPLACE INTO movies VALUES (?, ?, ?)", (code, data['caption'], data['file_id']))
        await db.commit()
    await state.clear()
    await message.answer(f"✅ Kino saqlandi! Kod: {code}", reply_markup=admin_menu)

# --- QIDIRUV VA MAJBURIY OBUNA ---
@dp.message(F.text)
async def search(message: Message):
    if not await check_sub(message.from_user.id):
        # Kanal linkiga / qo'shish
        kb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="📢 Kanalga a'zo bo'lish", url=f"https://t.me{CHANNELS[0].replace('@','')}") ]])
        return await message.answer("<b>Botingizdan foydalanish uchun kanalimizga a'zo bo'ling!</b>", reply_markup=kb)
    
    async with aiosqlite.connect("kino.db") as db:
        async with db.execute("SELECT caption, file_id FROM movies WHERE code = ?", (message.text.strip(),)) as cursor:
            movie = await cursor.fetchone()
    
    if movie:
        await message.answer_video(movie[1], caption=movie[0])
    else:
        await message.answer("😔 Kechirasiz, bunday kodli kino topilmadi.")

async def main():
    keep_alive()
    await init_db()
    await dp.start_polling(bot)

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    asyncio.run(main())
