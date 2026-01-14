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


# ---------- TASK LIST ----------
DAILY_TASKS = [
    "(1) 10 دقیقه مدیتیشن یا نفس عمیق",
    "(2) چک کردن جاب‌ها و 3 تا اپلای",
    "(3) 45 دقیقه درس Azure/Exam",
    "(4) 15 دقیقه استراحت و کشش",
    "(5) 30 دقیقه نتورکینگ/لینکدین",
    "(6) 20 دقیقه ورزش سبک",
]

STATE_FILE = "state.json"


# ---------- STATE HELPERS ----------
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


ALL_STATE = load_all_state()


def init_state(chat_id: int):
    key = str(chat_id)
    ALL_STATE[key] = {
        "index": 0,
        "later": [],
        "mode": "main",
        "extra_index": 0,
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
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("✅ انجام شد", callback_data="done"),
            InlineKeyboardButton("⏳ وقت اضافه", callback_data="later")
        ]
    ])


def build_start_keyboard():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("📋 گزارش امروز", callback_data="summary")]
    ])


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
    dn_main = len(done_main)
    dn_extra = len(done_extra)
    dn_total = dn_main + dn_extra
    un_done = len(pending)
    progress = int((dn_total / total) * 100)

    today_str = date.today().strftime("%Y-%m-%d")

    lines = []
    lines.append(f"📊 گزارش امروز ({today_str})\n")
    lines.append(f"• کل تسک‌ها: {total}")
    lines.append(f"• انجام‌شده: {dn_total}")
    if dn_extra > 0:
        lines.append(f"  └ از این‌ها در وقت اضافه: {dn_extra}")
    lines.append(f"• مانده برای بعد: {un_done}")
    lines.append(f"• درصد پیشرفت: {progress}%")
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
        lines.append("⏳ مانده برای فردا:")
        for t in pending:
            lines.append(f"  • {t}")
        lines.append("")
    else:
        lines.append("🎉 آفرین! همه انجام شد 👏")

    return "\n".join(lines)


# ---------- HANDLERS ----------
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🌱 سلام! من همراه روزانه‌ات هستم.\n"
        "با هم قدم‌به‌قدم جلو می‌ریم.\n\n"
        "دستورها:\n"
        "• /today شروع کارهای امروز\n"
        "• /summary گزارش روز\n\n"
        "اگر آماده‌ای، شروع کن 💪",
        reply_markup=build_start_keyboard()
    )


async def today(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    init_state(chat_id)
    state = get_state(chat_id)

    idx = state["index"]
    total = len(DAILY_TASKS)
    task = DAILY_TASKS[idx]

    text = (
        "🚀 شروع برنامه امروز!\n\n"
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
    await update.message.reply_text(build_summary_text(state))


async def handle_button(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    data = query.data
    await query.answer()

    chat_id = query.message.chat_id
    state = get_state(chat_id)

    if data == "summary":
        await query.edit_message_text(build_summary_text(state))
        return

    if state["mode"] == "main":
        await handle_main_round(query, state, data)
    else:
        await handle_extra_round(query, state, data)


async def handle_main_round(query, state, data):
    log = state["log"]
    current_index = state["index"] - 1

    if data == "done":
        log[current_index]["first"] = "done"
    elif data == "later":
        log[current_index]["first"] = "later"
        if current_index not in state["later"]:
            state["later"].append(current_index)

    total = len(DAILY_TASKS)

    if state["index"] < total:
        next_index = state["index"]
        task = DAILY_TASKS[next_index]
        text = f"🔹 تسک {next_index + 1} از {total}:\n{task}"

        await query.edit_message_text(text, reply_markup=build_task_keyboard())
        state["index"] += 1
        save_all_state()
    else:
        if state["later"]:
            state["mode"] = "extra"
            state["extra_index"] = 0

            later_list = state["later"]
            idx = later_list[state["extra_index"]]
            task = DAILY_TASKS[idx]

            text = f"⏱ وقت اضافه – راند دوم\n\n🔹 تسک 1 از {len(later_list)}:\n{task}"

            await query.edit_message_text(text, reply_markup=build_task_keyboard())
            save_all_state()
        else:
            await query.edit_message_text(build_summary_text(state))
            save_all_state()


async def handle_extra_round(query, state, data):
    log = state["log"]
    later_list = state["later"]

    current_pos = state["extra_index"]
    current_task_idx = later_list[current_pos]

    if data == "done":
        log[current_task_idx]["second"] = "done"
    elif data == "later":
        log[current_task_idx]["second"] = "later"

    state["extra_index"] += 1

    if state["extra_index"] < len(later_list):
        next_task_idx = later_list[state["extra_index"]]
        text = (
            f"⏱ وقت اضافه – راند دوم\n\n"
            f"🔹 تسک {state['extra_index'] + 1} از {len(later_list)}:\n"
            f"{DAILY_TASKS[next_task_idx]}"
        )
        await query.edit_message_text(text, reply_markup=build_task_keyboard())
        save_all_state()
    else:
        await query.edit_message_text(build_summary_text(state))
        save_all_state()


# ---------- MAIN ----------
def main():
    app = ApplicationBuilder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("today", today))
    app.add_handler(CommandHandler("summary", summary))
    app.add_handler(CallbackQueryHandler(handle_button))

    print("Bot running...")
    app.run_polling()


if __name__ == "__main__":
    main()
