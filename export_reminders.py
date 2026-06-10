#!/usr/bin/env python3
"""
YOYOBUILDS Productivity Dashboard — Reminders exporter.

Reads macOS Reminders via EventKit, classifies tasks into categories by
keyword, merges with existing data.json (history is never lost, even if
reminders are deleted in the app), and pushes the result to GitHub so
Vercel redeploys the dashboard.

Run manually once first to grant the Reminders privacy permission:
    python3 export_reminders.py
"""

import datetime
import json
import os
import subprocess
import sys

# ---------------------------------------------------------------------------
# Category keyword table — edit freely. First category whose keyword appears
# in the task title (case-insensitive) wins, in this order. Fallback: admin.
# ---------------------------------------------------------------------------
KEYWORDS = {
    "content": [
        "content", "post", "video", "reel", "edit", "film", "shoot", "script",
        "thumbnail", "caption", "ig", "instagram", "youtube", "tiktok", "blog",
        "newsletter", "podcast", "design", "draft", "write",
        "拍", "剪", "出post", "出片", "影片", "文案", "貼文", "內容",
    ],
    "biz": [
        "client", "meeting", "call", "invoice", "quote", "proposal", "pitch",
        "contract", "deal", "partner", "sponsor", "brand", "biz", "business",
        "傾", "報價", "開會", "客", "合作", "生意", "簽約",
    ],
    "life": [
        "gym", "run", "workout", "exercise", "yoga", "walk", "swim", "hike",
        "doctor", "dentist", "grocery", "groceries", "laundry", "clean",
        "cook", "dinner", "lunch", "birthday", "family", "friend",
        "運動", "跑步", "健身", "買餸", "睇醫生", "洗衫", "屋企", "朋友", "食飯",
    ],
    # everything else falls back to "admin"
}

REPO_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_PATH = os.path.join(REPO_DIR, "data.json")
LOG_PATH = os.path.expanduser("~/Library/Logs/yoyobuilds-dashboard.log")
HKT = datetime.timezone(datetime.timedelta(hours=8))
COMPLETED_LOOKBACK_DAYS = 90


def log(msg):
    stamp = datetime.datetime.now(HKT).strftime("%Y-%m-%d %H:%M:%S")
    line = f"[{stamp}] {msg}"
    print(line)
    try:
        with open(LOG_PATH, "a") as f:
            f.write(line + "\n")
    except OSError:
        pass


def classify(title):
    lowered = (title or "").lower()
    for cat, words in KEYWORDS.items():
        for w in words:
            if w.lower() in lowered:
                return cat
    return "admin"


# ---------------------------------------------------------------------------
# EventKit access
# ---------------------------------------------------------------------------

def fetch_reminders():
    from EventKit import EKEventStore, EKEntityTypeReminder
    from Foundation import NSDate, NSRunLoop, NSDefaultRunLoopMode, NSCalendar

    store = EKEventStore.alloc().init()

    state = {"done": False, "granted": False}

    def auth_cb(granted, error):
        state["granted"] = bool(granted)
        state["done"] = True

    if hasattr(store, "requestFullAccessToRemindersWithCompletion_"):
        store.requestFullAccessToRemindersWithCompletion_(auth_cb)
    else:
        store.requestAccessToEntityType_completion_(EKEntityTypeReminder, auth_cb)

    deadline = datetime.datetime.now() + datetime.timedelta(seconds=120)
    while not state["done"] and datetime.datetime.now() < deadline:
        NSRunLoop.currentRunLoop().runMode_beforeDate_(
            NSDefaultRunLoopMode, NSDate.dateWithTimeIntervalSinceNow_(0.1))

    if not state["granted"]:
        raise PermissionError(
            "Reminders access not granted. Open System Settings → Privacy & "
            "Security → Reminders and enable access for the app running this "
            "script (Terminal / python3), then re-run.")

    def run_predicate(predicate):
        result = {"done": False, "reminders": None}

        def cb(reminders):
            result["reminders"] = reminders
            result["done"] = True

        store.fetchRemindersMatchingPredicate_completion_(predicate, cb)
        fetch_deadline = datetime.datetime.now() + datetime.timedelta(seconds=60)
        while not result["done"] and datetime.datetime.now() < fetch_deadline:
            NSRunLoop.currentRunLoop().runMode_beforeDate_(
                NSDefaultRunLoopMode, NSDate.dateWithTimeIntervalSinceNow_(0.1))
        return result["reminders"] or []

    cal = NSCalendar.currentCalendar()

    def due_date_str(reminder):
        comps = reminder.dueDateComponents()
        if comps is None:
            return None
        nsdate = cal.dateFromComponents_(comps)
        if nsdate is None:
            return None
        dt = datetime.datetime.fromtimestamp(nsdate.timeIntervalSince1970(), HKT)
        return dt.strftime("%Y-%m-%d")

    incomplete_pred = store.predicateForIncompleteRemindersWithDueDateStarting_ending_calendars_(
        None, None, None)
    pending = []
    for r in run_predicate(incomplete_pred):
        title = str(r.title() or "").strip()
        if not title:
            continue
        item = {"title": title, "cat": classify(title)}
        due = due_date_str(r)
        if due:
            item["due"] = due
        pending.append(item)

    start = NSDate.dateWithTimeIntervalSinceNow_(-COMPLETED_LOOKBACK_DAYS * 86400)
    end = NSDate.dateWithTimeIntervalSinceNow_(86400)
    completed_pred = store.predicateForCompletedRemindersWithCompletionDateStarting_ending_calendars_(
        start, end, None)
    completed = []
    for r in run_predicate(completed_pred):
        title = str(r.title() or "").strip()
        cdate = r.completionDate()
        if not title or cdate is None:
            continue
        cdt = datetime.datetime.fromtimestamp(cdate.timeIntervalSince1970(), HKT)
        item = {
            "title": title,
            "completed": cdt.strftime("%Y-%m-%dT%H:%M:%S%z"),
            "cat": classify(title),
        }
        due = due_date_str(r)
        if due:
            item["due"] = due
        completed.append(item)

    return completed, pending


# ---------------------------------------------------------------------------
# Merge + persist + publish
# ---------------------------------------------------------------------------

def load_existing():
    try:
        with open(DATA_PATH) as f:
            data = json.load(f)
        if data.get("_sample"):
            return {"completed": [], "pending": []}
        return data
    except (OSError, ValueError):
        return {"completed": [], "pending": []}


def merge(existing_completed, new_completed):
    by_key = {}
    for item in existing_completed + new_completed:
        key = (item.get("title"), item.get("completed"))
        by_key[key] = item  # new export wins on identical key
    merged = list(by_key.values())
    merged.sort(key=lambda x: x.get("completed") or "", reverse=True)
    return merged


def git_publish():
    def git(*args, check=True):
        return subprocess.run(["git", *args], cwd=REPO_DIR, check=check,
                              capture_output=True, text=True)

    status = git("status", "--porcelain", "--", "data.json")
    if not status.stdout.strip():
        log("data.json unchanged — skipping commit/deploy.")
        return False
    git("add", "data.json")
    stamp = datetime.datetime.now(HKT).strftime("%Y-%m-%d %H:%M")
    git("commit", "-m", f"data: update {stamp} HKT")
    git("push")
    log("Pushed data.json to GitHub.")

    # The Vercel GitHub integration is not connected, so deploy via CLI.
    env = dict(os.environ, PATH="/usr/local/bin:" + os.environ.get("PATH", "/usr/bin:/bin"))
    deploy = subprocess.run(
        ["/usr/local/bin/npx", "-y", "vercel@54.11.1", "deploy", "--prod", "--yes"],
        cwd=REPO_DIR, env=env, capture_output=True, text=True, timeout=600)
    if deploy.returncode == 0:
        log("Vercel production deploy triggered OK.")
    else:
        log("Vercel deploy FAILED:\n" + (deploy.stderr or deploy.stdout)[-800:])
    return True


def main():
    log("--- export run started ---")
    new_completed, pending = fetch_reminders()
    log(f"Fetched {len(new_completed)} completed (last {COMPLETED_LOOKBACK_DAYS}d), "
        f"{len(pending)} pending.")

    existing = load_existing()
    completed = merge(existing.get("completed", []), new_completed)

    data = {
        "completed": completed,
        "pending": sorted(pending, key=lambda x: x.get("due") or "9999"),
        "last_updated": datetime.datetime.now(HKT).strftime("%Y-%m-%dT%H:%M:%S%z"),
    }

    # Only rewrite (and so only redeploy) when task data actually changed.
    old_core = {k: existing.get(k) for k in ("completed", "pending")}
    new_core = {"completed": data["completed"], "pending": data["pending"]}
    if json.loads(json.dumps(old_core)) == json.loads(json.dumps(new_core)):
        log("No task changes since last run — nothing to publish.")
        return

    with open(DATA_PATH, "w") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
        f.write("\n")
    log(f"Wrote data.json: {len(completed)} completed total, {len(pending)} pending.")
    git_publish()


if __name__ == "__main__":
    try:
        main()
    except Exception:
        log("ERROR:\n" + __import__("traceback").format_exc())
        sys.exit(1)
