#!/bin/zsh
# One-time setup for the YOYOBUILDS dashboard automation.
set -e
DIR="$(cd "$(dirname "$0")" && pwd)"

echo "── Installing Python EventKit bridge…"
/usr/bin/python3 -m pip install --user --quiet pyobjc-framework-EventKit

echo "── Wiring git auth through GitHub CLI…"
gh auth setup-git

echo "── Installing launchd agent (hourly 12:00–24:00)…"
PLIST=~/Library/LaunchAgents/com.yoyobuilds.dashboard.plist
mkdir -p ~/Library/LaunchAgents
cp "$DIR/com.yoyobuilds.dashboard.plist" "$PLIST"
launchctl bootout "gui/$(id -u)/com.yoyobuilds.dashboard" 2>/dev/null || true
launchctl bootstrap "gui/$(id -u)" "$PLIST"

echo "── Done. Now run the exporter once by hand to grant Reminders access:"
echo "   /usr/bin/python3 $DIR/export_reminders.py"
