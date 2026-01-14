import os
import json
from dotenv import load_dotenv
from telegram import (
    Update,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
    InputMediaPhoto,
)
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    CallbackQueryHandler,
    ContextTypes,
)

# ---------- load env ----------
load_dotenv()
BOT_TOKEN = os.getenv("BOT_TOKEN")

if not BOT_TOKEN:
    raise RuntimeError("BOT_TOKEN is not set in .env file")


# ---------- تنظیمات ----------
DAILY_TASKS = [
    "۱️⃣ 10 دقیقه مدیتیشن یا نفس عمیق.",
    "۲️⃣ چک کردن جاب‌ها و ۳ تا اپلای.",
    "۳️⃣ ۴۵ دقیقه درس (Azure/Exam).",
    "۴️⃣ ۱۵ دقیقه استراحت و کشش.",
    "۵️⃣ ۳۰ دقیقه نتورکینگ/لینکدین.",
    "۶️⃣ ۲۰ دقیقه ورزش سبک.",
]

# یک عکس تستی عمومی؛ بعداً لینک خودت را بگذار
TASK_IMAGE_URL = "https://placehold.co/600x400?text=Focus"

STATE_FILE = "state.json"


# ---------- مدیریت ذخیره state در فایل JSON ----------

def load_all_state():
    if not os.path.exists(STATE_FILE):
        return {}
    try:
        with open(STATE_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def save_all_state():
    with open(STATE_FILE, "w", encoding="utf-8") as f:
        json.dump(ALL_STATE, f, ensure_ascii=False, indent=2)


# ALL_STATE: key = chat_id (str) → state dict
ALL_STATE = load_all_state()


def init_state(chat_id: int):
    key = str(chat_id)
    ALL_STATE[key] = {
        "index": 0,          # در راند اصلی: اندیس تسک بعدی که باید نمایش داده شود
        "later": [],         # اندیس تسک‌هایی که رفتند برای وقت اضافه
        "mode": "main",      # "main" یا "extra"
        "extra_index": 0,    # در راند extra: اندیس فعلی در لیست later
        "log": [
            {"first": None, "second": None} for _ in range(len(DAILY_TASKS))
        ],
    }
    save_all_state()


def get_state(chat_id: int):
    key = str(chat_id)
    if key not in ALL_STATE:
        init_state(chat_id)
    return ALL_STATE[key]


def build_task_keyboard():
    keyboard = [
        [
            InlineKeyboardButton("✅ انجام شد", callback_data="done"),
            InlineKeyboardButton("⏳ وقت اضافه", callback_data="later"),
        ]
    ]
    return InlineKeyboardMarkup(keyboard)


def build_summary_text(state) -> str:
    log = state["log"]
    done_main = []
    done_extra = []
    pending = []

    for i, entry in enumerate(log):
        task_text = DAILY_TASKS[i]
        first = entry["first"]
        second = entry["second"]

        if second == "done":
            done_extra.append(task_text)
        elif first == "done":
            done_main.append(task_text)
        else:
            pending.append(task_text)

    lines = []
    lines.append("📊 گزارش امروز\n")

    if done_main:
        lines.append("✅ انجام‌شده در راند اصلی:")
        for t in done_main:
            lines.append(f"• {t}")
        lines.append("")

    if done_extra:
        lines.append("⏱ انجام‌شده در وقت اضافه:")
        for t in done_extra:
            lines.append(f"• {t}")
        lines.append("")

    if pending:
        lines.append("⏳ مانده برای بعد / فردا:")
        for t in pending:
            lines.append(f"• {t}")
        lines.append("")
    else:
        lines.append("🎉 هیچ کاری برای بعد نماند، همه انجام شد. آفرین 👏")

    return "\n".join(lines)


# ---------- handlers ----------

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "سلام، من بات برنامه‌ی روز هستم 🌱\n"
        "دستورها:\n"
        "/today  شروع برنامه‌ی امروز\n"
        "/summary  گزارش امروز\n\n"
        "برای هر تسک:\n"
        "✅ انجام شد → انجام‌شده\n"
        "⏳ وقت اضافه → فعلاً رد می‌کنی، ولی در وقت اضافه و گزارش میاد."
    )


async def today(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    init_state(chat_id)
    state = get_state(chat_id)

    idx = state["index"]
    task = DAILY_TASKS[idx]

    await update.message.reply_photo(
        photo=TASK_IMAGE_URL,
        caption=f"برنامه‌ی امروز شروع شد ✅\n\n{task}",
        reply_markup=build_task_keyboard(),
    )

    state["index"] += 1
    save_all_state()


async def summary(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    state = get_state(chat_id)
    summary_text = build_summary_text(state)
    await update.message.reply_text(summary_text)


async def handle_button(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    data = query.data
    await query.answer()

    chat_id = query.message.chat_id
    state = get_state(chat_id)

    if state["mode"] == "main":
        await handle_main_round(query, state, data)
    else:
        await handle_extra_round(query, state, data)


async def handle_main_round(query, state, data: str):
    log = state["log"]
    current_index = state["index"] - 1  # آخرین تسکی که نمایش داده شده

    # ثبت وضعیت این تسک در log
    if data == "done":
        log[current_index]["first"] = "done"
    elif data == "later":
        log[current_index]["first"] = "later"
        if current_index not in state["later"]:
            state["later"].append(current_index)

    # آیا هنوز در راند اصلی تسک باقی مانده؟
    if state["index"] < len(DAILY_TASKS):
        next_index = state["index"]
        task = DAILY_TASKS[next_index]

        await query.edit_message_media(
            media=InputMediaPhoto(
                media=TASK_IMAGE_URL,
                caption=task,
            ),
            reply_markup=build_task_keyboard(),
        )

        state["index"] += 1
        save_all_state()
    else:
        # راند اصلی تمام شد
        if state["later"]:
            # وارد راند وقت اضافه می‌شویم
            state["mode"] = "extra"
            state["extra_index"] = 0

            later_list = state["later"]
            idx = later_list[state["extra_index"]]
            task = f"⏱ وقت اضافه:\n\n{DAILY_TASKS[idx]}"

            await query.edit_message_media(
                media=InputMediaPhoto(
                    media=TASK_IMAGE_URL,
                    caption=task,
                ),
                reply_markup=build_task_keyboard(),
            )

            # extra_index نشان‌دهنده تسک فعلی در لیست later است
            save_all_state()
        else:
            # هیچ کاری برای وقت اضافه نداریم → مستقیم گزارش
            summary_text = build_summary_text(state)
            await query.edit_message_caption(summary_text)
            save_all_state()


async def handle_extra_round(query, state, data: str):
    log = state["log"]
    later_list = state["later"]

    # اگر لیست later خالی است، مستقیم گزارش بده
    if not later_list:
        summary_text = build_summary_text(state)
        await query.edit_message_caption(summary_text)
        save_all_state()
        return

    # اندیس فعلی در راند extra
    current_pos = state["extra_index"]
    if current_pos >= len(later_list):
        # یعنی همه را دیده‌ایم → گزارش
        summary_text = build_summary_text(state)
        await query.edit_message_caption(summary_text)
        save_all_state()
        return

    current_task_idx = later_list[current_pos]

    # ثبت وضعیت این تسک در log (second)
    if data == "done":
        log[current_task_idx]["second"] = "done"
    elif data == "later":
        log[current_task_idx]["second"] = "later"

    # رفتن به تسک بعدی در وقت اضافه
    state["extra_index"] += 1

    if state["extra_index"] < len(later_list):
        next_task_idx = later_list[state["extra_index"]]
        task = f"⏱ وقت اضافه:\n\n{DAILY_TASKS[next_task_idx]}"

        await query.edit_message_media(
            media=InputMediaPhoto(
                media=TASK_IMAGE_URL,
                caption=task,
            ),
            reply_markup=build_task_keyboard(),
        )

        save_all_state()
    else:
        # دیگر تسکی در وقت اضافه نمانده → گزارش نهایی
        summary_text = build_summary_text(state)
        await query.edit_message_caption(summary_text)
        save_all_state()


def main():
    app = ApplicationBuilder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("today", today))
    app.add_handler(CommandHandler("summary", summary))
    app.add_handler(CallbackQueryHandler(handle_button))

    print("Bot is running...")
    app.run_polling()


if __name__ == "__main__":
    main()
