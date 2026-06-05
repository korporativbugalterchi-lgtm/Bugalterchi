import logging
import asyncio
import json
import os
from datetime import datetime, timedelta
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import CommandStart, Command
from aiogram.types import (InlineKeyboardMarkup, InlineKeyboardButton,
                           ReplyKeyboardMarkup, KeyboardButton, ReplyKeyboardRemove,
                           FSInputFile)

# ==================== SOZLAMALAR ====================
BOT_TOKEN = "8326552518:AAGFiqzMTHwj-o65oUZ9UV_h63OgCXk0w6Q"
ADMIN_ID = 422549832
CHANNEL_LINK = "https://t.me/+YoUZme42QtA5MWE6"
CHANNEL_ID = -1001234567890

USERS_FILE = "users.json"
SCHEDULE_FILE = "schedule.json"
POSTS_FILE = "posts.json"
TIMED_FILE = "timed_posts.json"

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

# ==================== FAYL FUNKSIYALARI ====================

def load_json(filename):
    if os.path.exists(filename):
        with open(filename, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}

def save_json(filename, data):
    with open(filename, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

# ==================== OBUNA TEKSHIRISH ====================

async def check_subscription(user_id: int) -> bool:
    try:
        member = await bot.get_chat_member(CHANNEL_ID, user_id)
        return member.status not in ["left", "kicked", "banned"]
    except:
        return True

def sub_keyboard():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📢 Kanalga obuna bo'lish", url=CHANNEL_LINK)],
        [InlineKeyboardButton(text="✅ Obuna bo'ldim", callback_data="check_sub")]
    ])

def phone_keyboard():
    return ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text="📱 Telefon raqamimni ulashish", request_contact=True)]],
        resize_keyboard=True,
        one_time_keyboard=True
    )

# ==================== XUSH KELIBSIZ ====================

async def send_welcome(user_id: int, name: str):
    posts = load_json(POSTS_FILE)
    welcome = posts.get("welcome", {})
    if welcome.get("photo_id"):
        await bot.send_photo(user_id, photo=welcome["photo_id"], caption=welcome.get("text", ""), parse_mode="HTML")
    elif welcome.get("text"):
        await bot.send_message(user_id, welcome["text"], parse_mode="HTML")
    else:
        await bot.send_message(user_id,
            f"👋 Salom, <b>{name}</b>!\n\n<b>Bugalterchi</b> botiga xush kelibsiz! 🎉\n\n"
            f"📚 Buxgalteriya, soliq, moliya va biznes bo'yicha foydali materiallar joylashtiriladi.\n\n"
            f"🔔 Yangi materiallar kelganda xabar olasiz!", parse_mode="HTML")
    if welcome.get("voice_id"):
        await bot.send_voice(user_id, voice=welcome["voice_id"])

# ==================== START ====================

@dp.message(CommandStart())
async def start_handler(message: types.Message):
    users = load_json(USERS_FILE)
    uid = str(message.from_user.id)
    is_sub = await check_subscription(message.from_user.id)
    if not is_sub:
        await message.answer("👋 Salom!\n\nBotdan foydalanish uchun avval kanalga obuna bo'ling! 👇", reply_markup=sub_keyboard())
        return
    if uid in users and users[uid].get("phone"):
        await send_welcome(message.from_user.id, message.from_user.first_name or "Foydalanuvchi")
        return
    if uid not in users:
        users[uid] = {
            "id": message.from_user.id,
            "first_name": message.from_user.first_name or "",
            "last_name": message.from_user.last_name or "",
            "username": message.from_user.username or "",
            "phone": "",
            "joined": datetime.now().strftime("%Y-%m-%d %H:%M"),
            "left": "",
        }
        save_json(USERS_FILE, users)
    await message.answer(
        f"👋 Salom, <b>{message.from_user.first_name}</b>!\n\nDavom etish uchun telefon raqamingizni ulashing 👇",
        parse_mode="HTML", reply_markup=phone_keyboard())

# ==================== TELEFON ====================

@dp.message(F.contact)
async def contact_handler(message: types.Message):
    users = load_json(USERS_FILE)
    uid = str(message.from_user.id)
    if uid in users:
        users[uid]["phone"] = message.contact.phone_number
        users[uid]["joined"] = datetime.now().strftime("%Y-%m-%d %H:%M")
        save_json(USERS_FILE, users)
    await message.answer("✅ Rahmat!", reply_markup=ReplyKeyboardRemove())
    await send_welcome(message.from_user.id, message.from_user.first_name or "Foydalanuvchi")
    await schedule_posts_for_user(message.from_user.id)

# ==================== REJALIK POSTLAR (YANGI OBUNACHI) ====================

async def schedule_posts_for_user(user_id: int):
    posts = load_json(POSTS_FILE)
    schedule = load_json(SCHEDULE_FILE)
    uid = str(user_id)
    now = datetime.now()
    schedule[uid] = []

    # Postlarni vaqt bo'yicha saralash
    post_list = []
    for key, post in posts.items():
        if key.startswith("post_") and post.get("delay_hours") is not None:
            post_list.append((key, post))
    post_list.sort(key=lambda x: x[1]["delay_hours"])

    for key, post in post_list:
        delay_hours = post["delay_hours"]
        send_time = now + timedelta(hours=delay_hours)
        schedule[uid].append({
            "post_key": key,
            "send_time": send_time.strftime("%Y-%m-%d %H:%M"),
            "sent": False
        })
    save_json(SCHEDULE_FILE, schedule)

# ==================== SCHEDULER ====================

async def check_and_send_scheduled():
    while True:
        try:
            schedule = load_json(SCHEDULE_FILE)
            posts = load_json(POSTS_FILE)
            now = datetime.now()
            changed = False

            for uid, user_schedule in schedule.items():
                for item in user_schedule:
                    if item["sent"]:
                        continue
                    send_time = datetime.strptime(item["send_time"], "%Y-%m-%d %H:%M")
                    if now >= send_time:
                        post = posts.get(item["post_key"])
                        if post:
                            try:
                                if post.get("photo_id"):
                                    await bot.send_photo(int(uid), photo=post["photo_id"], caption=post.get("text", ""), parse_mode="HTML")
                                elif post.get("video_id"):
                                    await bot.send_video(int(uid), video=post["video_id"], caption=post.get("text", ""), parse_mode="HTML")
                                elif post.get("text"):
                                    await bot.send_message(int(uid), post["text"], parse_mode="HTML")
                                if post.get("voice_id"):
                                    await bot.send_voice(int(uid), voice=post["voice_id"])
                            except Exception as e:
                                logger.error(f"Scheduled send error {uid}: {e}")
                        item["sent"] = True
                        changed = True

            if changed:
                save_json(SCHEDULE_FILE, schedule)

            # Aniq vaqtli postlar
            timed = load_json(TIMED_FILE)
            timed_changed = False
            for pid, p in list(timed.items()):
                if p.get("sent"):
                    continue
                send_time = datetime.strptime(p["send_time"], "%Y-%m-%d %H:%M")
                if now >= send_time:
                    users = load_json(USERS_FILE)
                    for uid2 in users.keys():
                        try:
                            if p.get("photo_id"):
                                await bot.send_photo(int(uid2), photo=p["photo_id"], caption=p.get("text", ""), parse_mode="HTML")
                            elif p.get("video_id"):
                                await bot.send_video(int(uid2), video=p["video_id"], caption=p.get("text", ""), parse_mode="HTML")
                            elif p.get("text"):
                                await bot.send_message(int(uid2), p["text"], parse_mode="HTML")
                            if p.get("voice_id"):
                                await bot.send_voice(int(uid2), voice=p["voice_id"])
                            await asyncio.sleep(0.05)
                        except:
                            pass
                    timed[pid]["sent"] = True
                    timed_changed = True
            if timed_changed:
                save_json(TIMED_FILE, timed)

        except Exception as e:
            logger.error(f"Scheduler error: {e}")
        await asyncio.sleep(60)

# ==================== OBUNA CALLBACK ====================

@dp.callback_query(F.data == "check_sub")
async def check_sub_cb(callback: types.CallbackQuery):
    is_sub = await check_subscription(callback.from_user.id)
    if is_sub:
        await callback.message.delete()
        users = load_json(USERS_FILE)
        uid = str(callback.from_user.id)
        if uid in users and users[uid].get("phone"):
            await send_welcome(callback.from_user.id, callback.from_user.first_name or "")
        else:
            await callback.message.answer("✅ Obuna tasdiqlandi!\n\nEndi telefon raqamingizni ulashing 👇", reply_markup=phone_keyboard())
    else:
        await callback.answer("❌ Hali obuna bo'lmadingiz!", show_alert=True)

# ==================== ADMIN PANEL ====================

admin_state = {}

def scheduled_posts_keyboard():
    posts = load_json(POSTS_FILE)
    buttons = []
    for key, post in sorted(posts.items()):
        if not key.startswith("post_"):
            continue
        delay = post.get("delay_hours", 0)
        if delay < 24:
            delay_text = f"{int(delay)} soat"
        else:
            delay_text = f"{int(delay // 24)} kun"
        buttons.append([InlineKeyboardButton(
            text=f"✅ {key.replace('post_', '')}. ({delay_text})",
            callback_data=f"edit_post_{key.replace('post_', '')}"
        )])
    buttons.append([InlineKeyboardButton(text="➕ Yangi post qo'shish", callback_data="add_new_post")])
    buttons.append([InlineKeyboardButton(text="🔙 Orqaga", callback_data="back_admin")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)

@dp.message(Command("admin"))
async def admin_panel(message: types.Message):
    if message.from_user.id != ADMIN_ID:
        return
    users = load_json(USERS_FILE)
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=f"👥 A'zolar ({len(users)} ta)", callback_data="show_users")],
        [InlineKeyboardButton(text="📊 Excel eksport", callback_data="export_excel")],
        [InlineKeyboardButton(text="📢 Oddiy post (hozir)", callback_data="broadcast_now")],
        [InlineKeyboardButton(text="⏰ Rejalik post (aniq vaqt)", callback_data="broadcast_timed")],
        [InlineKeyboardButton(text="✏️ Xush kelibsiz xabarini sozlash", callback_data="set_welcome")],
        [InlineKeyboardButton(text="📋 Rejalik postlarni sozlash", callback_data="set_scheduled")],
    ])
    await message.answer(
        f"🔧 <b>Admin Panel</b>\n👥 Jami a'zolar: <b>{len(users)} ta</b>",
        reply_markup=keyboard, parse_mode="HTML")

# ==================== A'ZOLAR ====================

@dp.callback_query(F.data == "show_users")
async def show_users(callback: types.CallbackQuery):
    if callback.from_user.id != ADMIN_ID:
        return
    users = load_json(USERS_FILE)
    if not users:
        await callback.answer("Hozircha a'zo yo'q!", show_alert=True)
        return
    text = "👥 <b>A'zolar ro'yxati:</b>\n\n"
    for i, (uid, u) in enumerate(users.items(), 1):
        name = f"{u['first_name']} {u['last_name']}".strip() or "Nomsiz"
        username = f"@{u['username']}" if u.get('username') else "—"
        phone = u.get('phone') or "—"
        joined = u.get('joined', '—')
        left = u.get('left') or "Hali bor"
        text += f"{i}. <b>{name}</b>\n   📞 {phone} | 👤 {username}\n   📅 {joined} | Chiqdi: {left}\n\n"
    for chunk in [text[i:i+4000] for i in range(0, len(text), 4000)]:
        await callback.message.answer(chunk, parse_mode="HTML")
    await callback.answer()

# ==================== EXCEL ====================

@dp.callback_query(F.data == "export_excel")
async def export_excel(callback: types.CallbackQuery):
    if callback.from_user.id != ADMIN_ID:
        return
    users = load_json(USERS_FILE)
    if not users:
        await callback.answer("Hozircha a'zo yo'q!", show_alert=True)
        return
    try:
        import openpyxl
        from openpyxl.styles import Font, PatternFill, Alignment
        wb = openpyxl.Workbook()
        ws = wb.active
        ws.title = "A'zolar"
        headers = ["№", "Ismi", "Familiyasi", "Username", "Telefon", "Telegram ID", "Qo'shilgan", "Chiqgan"]
        for col, h in enumerate(headers, 1):
            cell = ws.cell(row=1, column=col, value=h)
            cell.font = Font(bold=True, color="FFFFFF")
            cell.fill = PatternFill(start_color="2E86AB", end_color="2E86AB", fill_type="solid")
            cell.alignment = Alignment(horizontal="center")
        for row, (uid, u) in enumerate(users.items(), 2):
            ws.cell(row=row, column=1, value=row-1)
            ws.cell(row=row, column=2, value=u.get('first_name', ''))
            ws.cell(row=row, column=3, value=u.get('last_name', ''))
            ws.cell(row=row, column=4, value=f"@{u['username']}" if u.get('username') else '')
            ws.cell(row=row, column=5, value=u.get('phone', ''))
            ws.cell(row=row, column=6, value=uid)
            ws.cell(row=row, column=7, value=u.get('joined', ''))
            ws.cell(row=row, column=8, value=u.get('left', ''))
        for col in ['A','B','C','D','E','F','G','H']:
            ws.column_dimensions[col].width = 18
        filename = f"azolar_{datetime.now().strftime('%Y%m%d_%H%M')}.xlsx"
        wb.save(filename)
        await callback.message.answer_document(FSInputFile(filename),
            caption=f"📊 <b>A'zolar ro'yxati</b>\n👥 Jami: {len(users)} ta", parse_mode="HTML")
        os.remove(filename)
    except ImportError:
        await callback.message.answer("❌ <code>pip install openpyxl</code> yozing!", parse_mode="HTML")
    await callback.answer()

# ==================== ODDIY POST ====================

@dp.callback_query(F.data == "broadcast_now")
async def broadcast_now(callback: types.CallbackQuery):
    if callback.from_user.id != ADMIN_ID:
        return
    admin_state[ADMIN_ID] = {"action": "broadcast_now"}
    await callback.message.answer("📢 <b>Hozir yuborish</b>\n\nPost yuboring (rasm+matn, video+matn, matn):\n/cancel - bekor qilish", parse_mode="HTML")
    await callback.answer()

# ==================== REJALIK POST (ANIQ VAQT) ====================

@dp.callback_query(F.data == "broadcast_timed")
async def broadcast_timed(callback: types.CallbackQuery):
    if callback.from_user.id != ADMIN_ID:
        return
    admin_state[ADMIN_ID] = {"action": "timed_wait_post"}
    await callback.message.answer("⏰ <b>Rejalik post</b>\n\nAvval postni yuboring:\n/cancel - bekor qilish", parse_mode="HTML")
    await callback.answer()

# ==================== XUSH KELIBSIZ SOZLASH ====================

@dp.callback_query(F.data == "set_welcome")
async def set_welcome(callback: types.CallbackQuery):
    if callback.from_user.id != ADMIN_ID:
        return
    admin_state[ADMIN_ID] = {"action": "set_welcome"}
    await callback.message.answer(
        "✏️ <b>Xush kelibsiz xabarini sozlash</b>\n\nRasm + matn yuboring (yoki faqat matn).\nOvozli xabar ham qo'shmoqchi bo'lsangiz, avval rasm+matn, keyin ovozli xabar yuboring.\n\n/cancel - bekor qilish",
        parse_mode="HTML")
    await callback.answer()

# ==================== REJALIK POSTLAR SOZLASH ====================

@dp.callback_query(F.data == "set_scheduled")
async def set_scheduled(callback: types.CallbackQuery):
    if callback.from_user.id != ADMIN_ID:
        return
    posts = load_json(POSTS_FILE)
    post_keys = [k for k in posts.keys() if k.startswith("post_")]
    buttons = []
    for key in sorted(post_keys):
        post = posts[key]
        delay = post.get("delay_hours", 0)
        delay_text = f"{int(delay)} soat" if delay < 24 else f"{int(delay // 24)} kun"
        buttons.append([InlineKeyboardButton(
            text=f"✅ {key} ({delay_text})",
            callback_data=f"view_post_{key}"
        )])
    buttons.append([InlineKeyboardButton(text="➕ Yangi post qo'shish", callback_data="add_new_post")])
    buttons.append([InlineKeyboardButton(text="🔙 Orqaga", callback_data="back_admin")])

    count = len(post_keys)
    await callback.message.answer(
        f"📋 <b>Rejalik postlar</b> ({count} ta)\n\nPostni bosib ko'ring yoki yangi qo'shing:",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons),
        parse_mode="HTML")
    await callback.answer()

# ==================== POST KO'RISH ====================

@dp.callback_query(F.data.startswith("view_post_"))
async def view_post(callback: types.CallbackQuery):
    if callback.from_user.id != ADMIN_ID:
        return
    post_key = callback.data.replace("view_post_", "")
    posts = load_json(POSTS_FILE)
    post = posts.get(post_key)
    if not post:
        await callback.answer("Post topilmadi!", show_alert=True)
        return

    delay = post.get("delay_hours", 0)
    delay_text = f"{int(delay)} soat" if delay < 24 else f"{int(delay // 24)} kun"
    await callback.message.answer(f"📌 <b>{post_key} ({delay_text}) — hozirgi holati:</b>", parse_mode="HTML")

    if post.get("photo_id"):
        await callback.message.answer_photo(photo=post["photo_id"], caption=post.get("text", "") or "Matn yo'q")
    elif post.get("video_id"):
        await callback.message.answer_video(video=post["video_id"], caption=post.get("text", "") or "Matn yo'q")
    elif post.get("text"):
        await callback.message.answer(post["text"])
    if post.get("voice_id"):
        await callback.message.answer_voice(voice=post["voice_id"])

    buttons = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✏️ Yangilash", callback_data=f"update_post_{post_key}")],
        [InlineKeyboardButton(text="🗑 O'chirish", callback_data=f"delete_post_{post_key}")],
        [InlineKeyboardButton(text="🔙 Orqaga", callback_data="set_scheduled")],
    ])
    await callback.message.answer("Nima qilmoqchisiz?", reply_markup=buttons)
    await callback.answer()

@dp.callback_query(F.data.startswith("update_post_"))
async def update_post(callback: types.CallbackQuery):
    if callback.from_user.id != ADMIN_ID:
        return
    post_key = callback.data.replace("update_post_", "")
    admin_state[ADMIN_ID] = {"action": "update_post", "post_key": post_key}
    await callback.message.answer(
        f"✏️ <b>{post_key} yangilash</b>\n\nYangi rasm+matn yoki video+matn yuboring:\n/cancel - bekor qilish",
        parse_mode="HTML")
    await callback.answer()

@dp.callback_query(F.data.startswith("delete_post_"))
async def delete_post_cb(callback: types.CallbackQuery):
    if callback.from_user.id != ADMIN_ID:
        return
    post_key = callback.data.replace("delete_post_", "")
    posts = load_json(POSTS_FILE)
    if post_key in posts:
        del posts[post_key]
        save_json(POSTS_FILE, posts)
    await callback.message.answer(f"🗑 <b>{post_key} o'chirildi!</b>", parse_mode="HTML")
    # Ro'yxatni qayta ko'rsatish
    post_keys = [k for k in posts.keys() if k.startswith("post_")]
    buttons = []
    for key in sorted(post_keys):
        p = posts[key]
        delay = p.get("delay_hours", 0)
        delay_text = f"{int(delay)} soat" if delay < 24 else f"{int(delay // 24)} kun"
        buttons.append([InlineKeyboardButton(text=f"✅ {key} ({delay_text})", callback_data=f"view_post_{key}")])
    buttons.append([InlineKeyboardButton(text="➕ Yangi post qo'shish", callback_data="add_new_post")])
    buttons.append([InlineKeyboardButton(text="🔙 Orqaga", callback_data="back_admin")])
    await callback.message.answer(
        f"📋 <b>Rejalik postlar</b> ({len(post_keys)} ta)",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons),
        parse_mode="HTML")
    await callback.answer()

# ==================== YANGI POST QO'SHISH ====================

@dp.callback_query(F.data == "add_new_post")
async def add_new_post(callback: types.CallbackQuery):
    if callback.from_user.id != ADMIN_ID:
        return
    admin_state[ADMIN_ID] = {"action": "add_post_wait_content"}
    await callback.message.answer(
        "➕ <b>Yangi rejalik post qo'shish</b>\n\n"
        "1. Avval postni yuboring (rasm+matn, video+matn, yoki faqat matn):\n\n"
        "/cancel - bekor qilish",
        parse_mode="HTML")
    await callback.answer()

@dp.callback_query(F.data == "back_admin")
async def back_admin(callback: types.CallbackQuery):
    if callback.from_user.id != ADMIN_ID:
        return
    users = load_json(USERS_FILE)
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=f"👥 A'zolar ({len(users)} ta)", callback_data="show_users")],
        [InlineKeyboardButton(text="📊 Excel eksport", callback_data="export_excel")],
        [InlineKeyboardButton(text="📢 Oddiy post (hozir)", callback_data="broadcast_now")],
        [InlineKeyboardButton(text="⏰ Rejalik post (aniq vaqt)", callback_data="broadcast_timed")],
        [InlineKeyboardButton(text="✏️ Xush kelibsiz xabarini sozlash", callback_data="set_welcome")],
        [InlineKeyboardButton(text="📋 Rejalik postlarni sozlash", callback_data="set_scheduled")],
    ])
    await callback.message.answer(
        f"🔧 <b>Admin Panel</b>\n👥 Jami a'zolar: <b>{len(users)} ta</b>",
        reply_markup=keyboard, parse_mode="HTML")
    await callback.answer()

# ==================== ADMIN XABARLAR ====================

@dp.message(Command("cancel"))
async def cancel_cmd(message: types.Message):
    if message.from_user.id == ADMIN_ID:
        admin_state.pop(ADMIN_ID, None)
        await message.answer("❌ Bekor qilindi. /admin - panelga qaytish")

@dp.message(F.from_user.id == ADMIN_ID)
async def admin_msg(message: types.Message):
    state = admin_state.get(ADMIN_ID)
    if not state:
        return
    action = state.get("action")

    # ---- ODDIY POST ----
    if action == "broadcast_now":
        admin_state.pop(ADMIN_ID, None)
        users = load_json(USERS_FILE)
        success = 0
        failed = 0
        await message.answer(f"📤 Yuborilmoqda... ({len(users)} ta a'zo)")
        for uid in users.keys():
            try:
                await message.copy_to(int(uid))
                success += 1
                await asyncio.sleep(0.05)
            except:
                failed += 1
        await message.answer(f"✅ Yuborildi!\n✅ {success} ta | ❌ {failed} ta")

    # ---- ANIQ VAQTLI POST — POST KUTISH ----
    elif action == "timed_wait_post":
        post_data = {}
        if message.photo:
            post_data["photo_id"] = message.photo[-1].file_id
            post_data["text"] = message.caption or ""
        elif message.video:
            post_data["video_id"] = message.video.file_id
            post_data["text"] = message.caption or ""
        elif message.text:
            post_data["text"] = message.text
        else:
            await message.answer("❌ Faqat rasm, video yoki matn yuboring!")
            return
        admin_state[ADMIN_ID] = {"action": "timed_wait_time", "post_data": post_data}
        await message.answer(
            "✅ Post qabul qilindi!\n\n⏰ Endi vaqtni yozing:\n<b>Format: YYYY-MM-DD HH:MM</b>\nMasalan: <code>2025-06-10 14:30</code>",
            parse_mode="HTML")

    # ---- ANIQ VAQTLI POST — VAQT KUTISH ----
    elif action == "timed_wait_time":
        try:
            send_time = datetime.strptime(message.text.strip(), "%Y-%m-%d %H:%M")
            if send_time <= datetime.now():
                await message.answer("⚠️ Bu vaqt o'tib ketgan! Kelajakdagi vaqt kiriting.\nMasalan: <code>2025-06-10 14:30</code>", parse_mode="HTML")
                return
            post_data = state["post_data"]
            post_data["send_time"] = send_time.strftime("%Y-%m-%d %H:%M")
            post_data["sent"] = False
            timed = load_json(TIMED_FILE)
            pid = str(int(datetime.now().timestamp()))
            timed[pid] = post_data
            save_json(TIMED_FILE, timed)
            admin_state.pop(ADMIN_ID, None)
            await message.answer(f"✅ Post rejalashtirildi!\n📅 Vaqt: <b>{send_time.strftime('%Y-%m-%d %H:%M')}</b>", parse_mode="HTML")
        except ValueError:
            await message.answer("❌ Noto'g'ri format!\nMasalan: <code>2025-06-10 14:30</code>", parse_mode="HTML")

    # ---- XUSH KELIBSIZ SOZLASH ----
    elif action == "set_welcome":
        posts = load_json(POSTS_FILE)
        if "welcome" not in posts:
            posts["welcome"] = {}
        if message.voice:
            posts["welcome"]["voice_id"] = message.voice.file_id
            save_json(POSTS_FILE, posts)
            admin_state.pop(ADMIN_ID, None)
            await message.answer("✅ Ovozli xabar saqlandi!")
        elif message.photo:
            posts["welcome"]["photo_id"] = message.photo[-1].file_id
            posts["welcome"]["text"] = message.caption or ""
            save_json(POSTS_FILE, posts)
            await message.answer("✅ Rasm saqlandi!\n\nOvozli xabar ham qo'shmoqchimisiz? Yuboring yoki /cancel bosing:")
        elif message.text:
            posts["welcome"]["text"] = message.text
            save_json(POSTS_FILE, posts)
            admin_state.pop(ADMIN_ID, None)
            await message.answer("✅ Matn saqlandi!")

    # ---- YANGI POST — KONTENT KUTISH ----
    elif action == "add_post_wait_content":
        post_data = {}
        if message.photo:
            post_data["photo_id"] = message.photo[-1].file_id
            post_data["text"] = message.caption or ""
        elif message.video:
            post_data["video_id"] = message.video.file_id
            post_data["text"] = message.caption or ""
        elif message.text:
            post_data["text"] = message.text
        else:
            await message.answer("❌ Faqat rasm, video yoki matn yuboring!")
            return
        admin_state[ADMIN_ID] = {"action": "add_post_wait_delay", "post_data": post_data}
        await message.answer(
            "✅ Post qabul qilindi!\n\n"
            "⏰ Endi vaqtni yozing — obunachi botga qo'shilganidan <b>necha vaqt keyin</b> yuborilsin?\n\n"
            "Misol:\n"
            "<code>0</code> — darhol\n"
            "<code>5 soat</code> — 5 soatdan keyin\n"
            "<code>3 kun</code> — 3 kundan keyin\n"
            "<code>10 kun</code> — 10 kundan keyin",
            parse_mode="HTML")

    # ---- YANGI POST — VAQT KUTISH ----
    elif action == "add_post_wait_delay":
        text = message.text.strip().lower()
        try:
            if text == "0" or text == "darhol":
                delay_hours = 0
            elif "soat" in text:
                delay_hours = float(text.replace("soat", "").strip())
            elif "kun" in text:
                delay_hours = float(text.replace("kun", "").strip()) * 24
            else:
                delay_hours = float(text)
        except:
            await message.answer("❌ Noto'g'ri format!\nMisol: <code>5 soat</code> yoki <code>3 kun</code>", parse_mode="HTML")
            return

        post_data = state["post_data"]
        post_data["delay_hours"] = delay_hours
        posts = load_json(POSTS_FILE)

        # Yangi kalit yaratish
        existing = [k for k in posts.keys() if k.startswith("post_")]
        new_index = len(existing) + 1
        post_key = f"post_{new_index}"
        posts[post_key] = post_data
        save_json(POSTS_FILE, posts)
        admin_state.pop(ADMIN_ID, None)

        delay_text = f"{int(delay_hours)} soat" if delay_hours < 24 else f"{int(delay_hours // 24)} kun"
        await message.answer(
            f"✅ <b>{post_key}</b> saqlandi!\n⏰ Vaqt: <b>{delay_text}</b> keyin yuboriladi",
            parse_mode="HTML")

    # ---- MAVJUD POST YANGILASH ----
    elif action == "update_post":
        post_key = state["post_key"]
        posts = load_json(POSTS_FILE)
        old_post = posts.get(post_key, {})

        if message.voice:
            old_post["voice_id"] = message.voice.file_id
            posts[post_key] = old_post
            save_json(POSTS_FILE, posts)
            admin_state.pop(ADMIN_ID, None)
            await message.answer(f"✅ {post_key} ovozli xabari yangilandi!")
        elif message.photo:
            old_post["photo_id"] = message.photo[-1].file_id
            old_post["text"] = message.caption or ""
            old_post.pop("video_id", None)
            posts[post_key] = old_post
            save_json(POSTS_FILE, posts)
            await message.answer("✅ Rasm yangilandi!\n\nOvozli xabar ham qo'shmoqchimisiz? Yuboring yoki /cancel bosing:")
        elif message.video:
            old_post["video_id"] = message.video.file_id
            old_post["text"] = message.caption or ""
            old_post.pop("photo_id", None)
            posts[post_key] = old_post
            save_json(POSTS_FILE, posts)
            admin_state.pop(ADMIN_ID, None)
            await message.answer(f"✅ {post_key} yangilandi!")
        elif message.text:
            old_post["text"] = message.text
            posts[post_key] = old_post
            save_json(POSTS_FILE, posts)
            admin_state.pop(ADMIN_ID, None)
            await message.answer(f"✅ {post_key} matni yangilandi!")

# ==================== BOTDAN CHIQISH ====================

@dp.my_chat_member()
async def user_left(event: types.ChatMemberUpdated):
    if event.new_chat_member.status in ["kicked", "left"]:
        users = load_json(USERS_FILE)
        uid = str(event.from_user.id)
        if uid in users:
            users[uid]["left"] = datetime.now().strftime("%Y-%m-%d %H:%M")
            save_json(USERS_FILE, users)

# ==================== ODDIY XABARLAR ====================

@dp.message()
async def any_msg(message: types.Message):
    if message.from_user.id == ADMIN_ID:
        return
    is_sub = await check_subscription(message.from_user.id)
    if not is_sub:
        await message.answer("⚠️ Botdan foydalanish uchun kanalga obuna bo'ling!", reply_markup=sub_keyboard())
        return
    await message.answer(
        "📩 Savolingiz yoki muammoingiz bo'lsa, @bugalterchi ga murojaat qiling! 👆"
    )

# ==================== ISHGA TUSHIRISH ====================

async def main():
    logger.info("Bot ishga tushdi!")
    asyncio.create_task(check_and_send_scheduled())
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
