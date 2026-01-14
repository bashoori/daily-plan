# state_manager.py
import os
import json
import time
from datetime import date
from settings import STATE_FILE, DAILY_TASKS

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
        "current_start": None,
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

def start_timer(state):
    state["current_start"] = time.time()

def stop_timer(state) -> int:
    start_ts = state.get("current_start")
    if not start_ts:
        return 0
    elapsed_sec = time.time() - start_ts
    state["current_start"] = None
    minutes = int(elapsed_sec / 60)
    return max(minutes, 1)

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
