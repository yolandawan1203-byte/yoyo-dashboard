# YOYOBUILDS Productivity Dashboard

Fully-automated productivity dashboard: macOS Reminders → Python → GitHub → Vercel.

**Live:** the Vercel URL is the bookmark — every refresh fetches the latest `data.json`.

## How it works

```
MacBook Reminders (iCloud-synced with iPhone)
   ↓  launchd, hourly 12:00–24:00 HKT
export_reminders.py  — reads via EventKit, classifies by keyword, merges history
   ↓  git commit + push (only when data changed)
GitHub repo → Vercel auto-redeploy
   ↓
index.html fetches /data.json on every load
```

- **History is never lost.** Each run merges new completions into `data.json`;
  deleting old reminders in the app does not remove them from the dashboard.
  Git history is a second backup.
- **All time analytics are based on completion timestamps** — Apple Reminders
  stores no start/end time or duration.

## Files

| File | Purpose |
|---|---|
| `index.html` | The dashboard (single file, no build step) |
| `data.json` | Exported task data, committed by the script |
| `export_reminders.py` | Reader / classifier / publisher |
| `com.yoyobuilds.dashboard.plist` | launchd schedule (hourly 12:00–24:00) |
| `yoyosync.c` | Source for `YoyoSync.app`, the launcher launchd runs |
| `setup.sh` | One-time install: deps + git auth + app build + launchd |

> **Why YoyoSync.app and why the repo lives at `~/yoyo-dashboard`:** launchd jobs
> can't read `~/Documents` (macOS folder protection) and a bare `python3` gets
> silently denied Reminders access in the launchd context. The repo therefore
> lives outside Documents, and launchd runs a tiny signed app wrapper that owns
> the Reminders permission and spawns the Python exporter.

## Editing the category keywords

Open `export_reminders.py` — the `KEYWORDS` dict at the top maps title keywords
(English + 中文) to `content` / `biz` / `life`. Anything unmatched falls back to
`admin`. First match wins, in dict order. Edit and save; the next hourly run
picks it up.

## Troubleshooting

- **Log:** `~/Library/Logs/yoyobuilds-dashboard.log`
- **"Reminders access not granted"** — System Settings → Privacy & Security →
  Reminders → enable **YoyoSync** (for scheduled runs) or **Terminal** (for
  manual runs), then retry.
- **Run the export immediately:** `launchctl kickstart gui/$(id -u)/com.yoyobuilds.dashboard`
- **Mac asleep at the top of the hour?** launchd runs the job at next wake.
- **Dashboard stale?** Check the LAST SYNC stamp in the header; then the log;
  then Vercel's deployments page.

## Local preview

```sh
python3 -m http.server 8000   # then open http://localhost:8000
```
