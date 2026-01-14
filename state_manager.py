# state_manager.py
import os
import json
import time
from datetime import date

from settings import STATE_FILE, DAILY_TASKS


# ---------- helpers for loading/saving ----------

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


# key = chat_id (str)
ALL_STATE = load_all_state()


def init_state(chat_id: int):
    """reset daily state for a chat"""
    key = str(chat_id)
    ALL_STATE[key] = {
        "index": 0,          # next task index in main round
        "later": [],         # task indices that were postponed
        "mode": "main",      # "main" or "extra"
        "extra_index": 0,    # pointer into later list
        "current_start": None,  # timestamp for running timer
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


# ---------- timer helpers ----------

def start_timer(state):
    state["current_start"] = time.time()


def stop_timer(state) -> int:
    """stop timer, return elapsed minutes (>= 0), and clear start"""
    start_ts = state.get("current_start")
    if not start_ts:
        return 0
    elapsed_sec = time.time() - start_ts
    state["current_start"] = None
    minutes = int(elapsed_sec / 60)
    return max(minutes, 1)  # at least 1 minute if non-zero


# ---------- summary text builder ----------

def build_summary_text(state) -> str:
    log = state["log"]

    done_main = []   # list of (task_text, minutes)
    done_extra = []  # list of (task_text, minutes)
    pending = []     # list of task_text

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

    total_tasks = len(DAILY_TASKS)
    n_main = len(done_main)
    n_extra = len(done_extra)
    n_done = n_main + n_extra
    n_pending = len(pending)
    progress = int((n_done / total_tasks) * 100) if total_tasks else 0
    total_focus = total_main_minutes + total_extra_minutes

    today_str = date.today().strftime("%Y-%m-%d")

    lines: list[str] = []

    # header
    lines.append(f"📊 گزارش امروز ({today_str})")
    lines.append("")
    lines.append(f"• کل تسک‌ها: {total_tasks}")
    lines.append(f"• انجام‌شده: {n_done}")
    if n_extra > 0:
        lines.append(f"  └ از این‌ها در وقت اضافه: {n_extra}")
    lines.append(f"• مانده برای بعد: {n_pending}")
    lines.append(f"• درصد پیشرفت: {progress}%")
    lines.append(f"• مجموع زمان فوکوس: {total_focus} دقیقه")
    lines.append("")

    # main round
    if done_main:
        lines.append("✅ انجام‌شده در راند اصلی:")
        lines.append("")
        for text, mins in done_main:
            extra = f"  (~{mins} دقیقه)" if mins else ""
            lines.append(f"• {text}{extra}")
            lines.append("")  # blank line between tasks

    # extra round
    if done_extra:
        lines.append("⏱ انجام‌شده در وقت اضافه:")
        lines.append("")
        for text, mins in done_extra:
            extra = f"  (~{mins} دقیقه)" if mins else ""
            lines.append(f"• {text}{extra}")
            lines.append("")

    # pending
    if pending:
        lines.append("⏳ مانده برای فردا:")
        lines.append("")
        for text in pending:
            lines.append(f"• {text}")
            lines.append("")
    else:
        lines.append("🎉 آفرین! همه‌ی پلن امروز را زدی 👏")

    return "\n".join(lines)
