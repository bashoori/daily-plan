import os
import json
import time
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


# ---------- DAILY PLAN TASKS ----------
DAILY_TASKS = [
    "۰۷:۰۰ – بیدار شدن، صبح سبک (۱۰ دقیقه کشش، آب، قهوه).\n"
    "بدن روشن = ذهن روشن.",

    "۰۷:۳۰ – جستجوی شغل و برنامه‌ریزی (۳۰ دقیقه).\n"
    "فقط سه خروجی: ۱) چه شغل‌هایی باز شده؟ ۲) کدام ۲ تا امروز اپلای می‌کنی؟ "
    "۳) چه رزومه/کاور لتر باید ویرایش شود؟",

    "۰۸:۰۰ – رزومه و اپلای (۹۰ دقیقه).\n"
    "هر روز فقط ۲–۳ شغل، ولی دقیق و هدف‌گذاری‌شده برای: "
    "TransLink، VCH، Fraser Health، شهرداری‌ها، نقش‌های junior DE/BI و Microsoft مناسب.",

    "۰۹:۳۰ – پیگیری و شبکه‌سازی (۳۰–۴۵ دقیقه).\n"
    "یک پیام کوتاه: دو کانکشن قبلی + یک نفر جدید. بدون فشار – فقط جرقه‌ی کوچک.",

    "۱۰:۳۰ – استراحت / پیاده‌روی کوتاه (۲۰ دقیقه).\n"
    "تنفس عمیق و ریست ذهن.",

    "۱۱:۰۰ – یادگیری برای افزایش شانس (۹۰ دقیقه).\n"
    "یک موضوع در روز؛ نمونه‌ها: Azure Fundamentals، SQL performance، ADF/Synapse overview، "
    "Power BI، یا تمرین STAR برای داستان‌ها.",

    "۱۲:۳۰ – ناهار و استراحت واقعی.\n"
    "بدون عذاب وجدان، این هم بخشی از کار پیدا کردن است.",

    "۱۴:۰۰ – پروژه نمونه / تمرین مهارت (۹۰ دقیقه).\n"
    "چیزی که بتوانی نشان بدهی: یک pipeline کوچک، یک Power BI report، یا یک notebook تمیز در GitHub. "
    "هدف: هر هفته یک خروجی قابل ارائه.",

    "۱۵:۳۰ – استراحت کوتاه (۱۵ دقیقه).",

    "۱۵:۴۵ – تمرین مصاحبه (۶۰ دقیقه).\n"
    "تمرین STAR بلندبلند: «چی کردم → چرا مهم بود → نتیجه چی شد». "
    "این بخش اعتماد به نفس می‌سازد.",

    "۱۷:۰۰ – پایان بخش کاری روز.\n"
    "بقیه‌ی روز برای زندگی، همسر، دوستان، و سوخت‌گیری.",

    "۲۰:۳۰ – پیگیری آرام، بدون فشار (۳۰ دقیقه).\n"
    "ایمیل‌ها، قبول کانکشن‌ها، جواب‌های لینکدین. نه کار سنگین، فقط نگه‌داشتن جریان.",

    "۲۲:۳۰ – آماده شدن برای خواب.\n"
    "خواب خوب = بزرگ‌ترین میانبر برای سریع‌تر کار پیدا کردن.",
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


# ALL_STATE: key = chat_id (str) → state dict
ALL_STATE = load_all_state()


def init_state(chat_id: int):
    key = str(chat_id)
    ALL_STATE[key] = {
        "index": 0,          # در راند اصلی: اندیس تسک بعدی
        "later": [],         # تسک‌های فرستاده‌شده به وقت اضافه (اندیس‌ها)
        "mode": "main",      # "main" یا "extra"
        "extra_index": 0,    # موقعیت فعلی در لیست later در راند دوم
        "current_start": None,  # زمان شروع تسک فعلی (timestamp)
        "log": [
            {"first": None, "second": None, "t_main": 0, "t_extra": 0}
            for _ in range(len(DAILY_TASKS))
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
            InlineKeyboardButton("⏳ وقت اضافه", callback_data="later"),
        ]
    ])


def build_start_keyboard():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("📋 گزارش امروز", callback_data="summary")]
    ])


def build_summary_text(state) -> str:
    log = state["log"]
    done_main, done_extra, pending = [], [], []

    total_main_minutes = 0
    total_extra_minutes = 0

    for i, entry in enumerate(log):
        task_text = DAILY_TASKS[i]
        first = entry["first"]
        second = entry["second"]
        t_main = entry.get("t_main", 0) or 0
        t_extra = entry.get("t_extra", 0) or 0

        total_main_minutes += t_main
        total_extra_minutes += t_extra

        if second == "done":
            done_extra.append((task_text, t_extra))
        elif first == "done":
            done_main.append((task_text, t_main))
        else:
            pending.append(task_text)

    total = len(DAILY_TASKS)
    dn_main = len(done_main)
    dn_extra = len(done_extra)
    dn_total = dn_main + dn_extra
    un_done = len(pending)
    progress = int((dn_total / total) * 100) if total else 0

    total_focus = total_main_minutes + total_extra_minutes

    today_str = date.today().strftime("%Y-%m-%d")

    lines = []
    lines.append(f"📊 گزارش امروز ({today_str})\n")
    lines.append(f"• کل تسک‌ها: {total}")
    lines.append(f"• انجام‌شده: {dn_total}")
    if dn_extra > 0:
        lines.append(f"  └ از این‌ها در وقت اضافه: {dn_extra}")
    lines.append(f"• مانده برای بعد: {un_done}")
    lines.append(f"• درصد پیشرفت: {progress}%")
    lines.append(f"• مجموع زمان فوکوس: {total_focus} دقیقه")
    lines.append("")

    if done_main:
        lines.append("✅ انجام‌شده در راند اصلی:")
        for t, m in done_main:
            extra = f"  (~{m} دقیقه)" if m else ""
            lines.append(f"  • {t}{extra}")
        lines.append("")

    if done_extra:
        lines.append("⏱ انجام‌شده در وقت اضافه:")
        for t, m in done_extra:
            extra = f"  (~{m} دقیقه)" if m else ""
            lines.append(f"  • {t}{extra}")
        lines.append("")

    if pending:
        lines.append("⏳ مانده برای فردا:")
        for t in pending:
            lines.append(f"  • {t}")
        lines.append("")
    else:
        lines.append("🎉 آفرین! همه‌ی پلن امروز را زدی 👏")

    return "\n".join(lines)


def start_timer(state):
    state["current_start"] = time.time()


def stop_timer(state):
    """زمان سپری‌شده را (به دقیقه) برمی‌گرداند و تایمر را صفر می‌کند."""
    start_ts = state.get("current_start")
    if not start_ts:
        return 0
    elapsed_sec = time.time() - start_ts
    state["current_start"] = None
    minutes = int(elapsed_sec / 60)
    return max(minutes, 1)  # حداقل ۱ دقیقه، که خالی نباشد


# ---------- HANDLERS ----------
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🌱 سلام! من همراه روزانه‌ات برای پیدا کردن کار هستم.\n"
        "نیم‌روز اول = کار پیدا کردن\n"
        "نیم‌روز دوم = یادگیری و پروژه\n"
        "شب = شبکه‌سازی و پیگیری\n\n"
        "دستورها:\n"
        "• /today  شروع پلن امروز\n"
        "• /summary  گزارش امروز\n\n"
        "اگر آماده‌ای، از /today شروع کن یا برای دیدن وضعیت فعلی روی دکمه زیر بزن.",
        reply_markup=build_start_keyboard(),
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
        f"{task}"
    )

    await update.message.reply_text(
        text,
        reply_markup=build_task_keyboard(),
    )

    start_timer(state)
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


async def handle_main_round(query, state, data: str):
    log = state["log"]
    current_index = state["index"] - 1

    # محاسبه‌ی زمان صرف‌شده برای این تسک در راند اصلی
    elapsed_min = stop_timer(state)
    if 0 <= current_index < len(log):
        log[current_index]["t_main"] = elapsed_min

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
            f"{task}"
        )

        await query.edit_message_text(
            text=text,
            reply_markup=build_task_keyboard(),
        )

        state["index"] += 1
        start_timer(state)
        save_all_state()
    else:
        # پایان راند اصلی
        if state["later"]:
            state["mode"] = "extra"
            state["extra_index"] = 0

            later_list = state["later"]
            idx = later_list[state["extra_index"]]
            task = DAILY_TASKS[idx]

            text = (
                "⏱ وقت اضافه – راند دوم\n\n"
                f"🔹 تسک ۱ از {len(later_list)}:\n"
                f"{task}"
            )

            await query.edit_message_text(
                text=text,
                reply_markup=build_task_keyboard(),
            )

            start_timer(state)
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

    # زمان صرف‌شده در راند دوم
    elapsed_min = stop_timer(state)
    log[current_task_idx]["t_extra"] = elapsed_min

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

        start_timer(state)
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

    print("Bot is running...")
    app.run_polling()


if __name__ == "__main__":
    main()
