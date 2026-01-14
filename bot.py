# bot.py
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

from settings import BOT_TOKEN, DAILY_TASKS
from state_manager import (
    get_state,
    init_state,
    start_timer,
    stop_timer,
    build_summary_text,
    save_all_state,
)

def build_start_keyboard():
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("▶️ شروع", callback_data="start"),
            InlineKeyboardButton("⏳ رد / وقت اضافه", callback_data="later"),
        ]
    ])

def build_running_keyboard():
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("✅ انجام شد", callback_data="done"),
            InlineKeyboardButton("⏳ رد / وقت اضافه", callback_data="later"),
        ]
    ])

def build_summary_button():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("📋 گزارش امروز", callback_data="summary")]
    ])

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🌱 سلام! من همراه روزانه‌ات برای پیدا کردن کار هستم.\n"
        "نیم‌روز اول = کار پیدا کردن\n"
        "نیم‌روز دوم = یادگیری و پروژه\n"
        "شب = شبکه‌سازی و پیگیری\n\n"
        "دستورها:\n"
        "• /today  شروع پلن امروز\n"
        "• /summary  گزارش امروز\n\n"
        "اگر آماده‌ای، از /today شروع کن یا برای دیدن وضعیت فعلی روی دکمه‌ی زیر بزن.",
        reply_markup=build_summary_button(),
    )

async def today(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    init_state(chat_id)
    state = get_state(chat_id)

    idx = state["index"]
    total = len(DAILY_TASKS)
    task = DAILY_TASKS[idx]

    text = (
        "🚀 شروع برنامه‌ی امروز.\n\n"
        f"🔹 تسک {idx + 1} از {total}:\n"
        f"{task}\n\n"
        "وقتی واقعاً شروع کردی، روی «▶️ شروع» بزن."
    )

    await update.message.reply_text(
        text,
        reply_markup=build_start_keyboard(),
    )

    state["index"] += 1
    state["current_start"] = None
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

    if data == "start":
        start_timer(state)
        await query.edit_message_reply_markup(reply_markup=build_running_keyboard())
        save_all_state()
        return

    if state["mode"] == "main":
        await handle_main_round(query, state, data)
    else:
        await handle_extra_round(query, state, data)

async def handle_main_round(query, state, data: str):
    log = state["log"]
    current_index = state["index"] - 1

    elapsed_min = stop_timer(state)
    if 0 <= current_index < len(log) and elapsed_min > 0:
        log[current_index]["t_main"] += elapsed_min

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
        text = (
            f"🔹 تسک {next_index + 1} از {total}:\n"
            f"{task}\n\n"
            "وقتی واقعاً شروع کردی، روی «▶️ شروع» بزن."
        )

        await query.edit_message_text(
            text=text,
            reply_markup=build_start_keyboard(),
        )

        state["index"] += 1
        state["current_start"] = None
        save_all_state()
    else:
        if state["later"]:
            state["mode"] = "extra"
            state["extra_index"] = 0

            later_list = state["later"]
            idx = later_list[state["extra_index"]]
            task = DAILY_TASKS[idx]

            text = (
                "⏱ وقت اضافه – راند دوم\n\n"
                f"🔹 تسک ۱ از {len(later_list)}:\n"
                f"{task}\n\n"
                "وقتی واقعاً شروع کردی، روی «▶️ شروع» بزن."
            )

            await query.edit_message_text(
                text=text,
                reply_markup=build_start_keyboard(),
            )

            state["current_start"] = None
            save_all_state()
        else:
            await query.edit_message_text(build_summary_text(state))
            save_all_state()

async def handle_extra_round(query, state, data: str):
    log = state["log"]
    later_list = state["later"]

    if not later_list:
        await query.edit_message_text(build_summary_text(state))
        save_all_state()
        return

    current_pos = state["extra_index"]
    if current_pos >= len(later_list):
        await query.edit_message_text(build_summary_text(state))
        save_all_state()
        return

    current_task_idx = later_list[current_pos]

    elapsed_min = stop_timer(state)
    if elapsed_min > 0:
        log[current_task_idx]["t_extra"] += elapsed_min

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
            f"{task}\n\n"
            "وقتی واقعاً شروع کردی، روی «▶️ شروع» بزن."
        )

        await query.edit_message_text(
            text=text,
            reply_markup=build_start_keyboard(),
        )

        state["current_start"] = None
        save_all_state()
    else:
        await query.edit_message_text(build_summary_text(state))
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
