import os
import json
from datetime import date
from dotenv import load_dotenv
from telegram import (
    Update,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
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
        "index": 0,          # در راند اصلی: اندیس تسک بعدی
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

    total = len(DAILY_TASKS)
    count_done_main = len(done_main)
    count_done_extra = len(done_extra)
    count_done_total = count_done_main + count_done_extra
    count_pending = len(pending)

    progress = int((count_done_total / total) * 100) if total > 0 else 0

    today_str = date.today().strftime("%Y-%m-%d")

    lines = []
    lines.append(f"📊 گزارش امروز ({today_str})\n")
    lines.append(f"• کل تسک‌ها: {total}")
    lines.append(f"• انجام‌شده: {count_done_total}")
    if count_done_extra > 0:
        lines.append(f"  └ از این‌ها در وقت اضافه: {count_done_extra}")
    lines.append(f"• مانده برای بعد: {count_pending}")
    lines.append(f"• درصد پیشرفت: {progress}٪")
    lines.append("")

    if done_main:
        lines.append("✅ انجام‌شده در راند اصلی:")
        for t in done_main:
            lines.append(f"  • {t}")
        lines.append("")

    if done_extra:
        lines.append("⏱ انجام‌شده در وقت اضافه:")
        for t in done_extra:
            lines.append(f"  • {t}")
        lines.append("")

    if pending:
        lines.append("⏳ مانده برای فردا / وقت اضافه:")
        for t in pending:
            lines.append(f"  • {t}")
        lines.append("")
    else:
        lines.append("🎉 هیچ کاری برای بعد نماند، همه انجام شد. آفرین 👏")

    return "\n".join(lines)


# ---------- handlers ----------

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "سلام، من بات برنامه‌ی روز هستم 🌱\n\n"
        "دستورها:\n"
        "• /today  شروع برنامه‌ی امروز\n"
        "• /summary  خلاصه و گزارش امروز\n\n"
        "برای هر تسک:\n"
        "✅ «انجام شد» → یعنی واقعاً انجامش دادی.\n"
        "⏳ «وقت اضافه» → یعنی الان رد می‌کنی، ولی در راند دوم و گزارش شب میاد."
    )


async def today(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    init_state(chat_id)
    state = get_state(chat_id)

    idx = state["index"]
    total = len(DAILY_TASKS)
    task = DAILY_TASKS[idx]

    text = (
        "🌱 برنامه‌ی امروز شروع شد.\n\n"
        f"🔹 تسک {idx + 1} از {total}:\n"
        f"{task}"
    )

    await update.message.reply_text(
        text,
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

    total = len(DAILY_TASKS)

    # آیا هنوز در راند اصلی تسک باقی مانده؟
    if state["index"] < total:
        next_index = state["index"]
        task = DAILY_TASKS[next_index]

        text = (
            f"🔹 تسک {next_index + 1} از {total}:\n"
            f"{task}"
        )

        await query.edit_message_text(
            text=text,
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
            task = DAILY_TASKS[idx]

            text = (
                "⏱ وقت اضافه – راند دوم\n\n"
                f"🔹 تسک {state['extra_index'] + 1} از {len(later_list)}:\n"
                f"{task}"
            )

            await query.edit_message_text(
                text=text,
                reply_markup=build_task_keyboard(),
            )

            save_all_state()
        else:
            # هیچ کاری برای وقت اضافه نداریم → مستقیم گزارش
            summary_text = build_summary_text(state)
            await query.edit_message_text(summary_text)
            save_all_state()


async def handle_extra_round(query, state, data: str):
    log = state["log"]
    later_list = state["later"]

    if not later_list:
        summary_text = build_summary_text(state)
        await query.edit_message_text(summary_text)
        save_all_state()
        return

    current_pos = state["extra_index"]
    if current_pos >= len(later_list):
        summary_text = build_summary_text(state)
        await query.edit_message_text(summary_text)
        save_all_state()
        return

    current_task_idx = later_list[current_pos]

    if data == "done":
        log[current_task_idx]["second"] = "done"
    elif data == "later":
        log[current_task_idx]["second"] = "later"

    state["extra_index"] += 1

    if state["extra_index"] < len(later_list):
        next_task_idx = later_list[state["extra_index"]]
        task = DAILY_TASKS[next_task_idx]

        text = (
            "⏱ وقت اضافه – راند دوم\n\n"
            f"🔹 تسک {state['extra_index'] + 1} از {len(later_list)}:\n"
            f"{task}"
        )

        await query.edit_message_text(
            text=text,
            reply_markup=build_task_keyboard(),
        )

        save_all_state()
    else:
        summary_text = build_summary_text(state)
        await query.edit_message_text(summary_text)
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
