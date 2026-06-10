#!/bin/zsh
# One-time setup for the YOYOBUILDS dashboard automation.
set -e
DIR="$(cd "$(dirname "$0")" && pwd)"

echo "── Installing Python EventKit bridge…"
/usr/bin/python3 -m pip install --user --quiet pyobjc-framework-EventKit

echo "── Wiring git auth through GitHub CLI…"
gh auth setup-git

echo "── Building YoyoSync.app wrapper (gives launchd a TCC identity for Reminders)…"
mkdir -p "$DIR/YoyoSync.app/Contents/MacOS"
clang -o "$DIR/YoyoSync.app/Contents/MacOS/YoyoSync" "$DIR/yoyosync.c"
cat > "$DIR/YoyoSync.app/Contents/Info.plist" <<'PLIST'
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>CFBundleIdentifier</key><string>com.yoyobuilds.sync</string>
  <key>CFBundleName</key><string>YoyoSync</string>
  <key>CFBundleExecutable</key><string>YoyoSync</string>
  <key>CFBundlePackageType</key><string>APPL</string>
  <key>CFBundleShortVersionString</key><string>1.0</string>
  <key>LSUIElement</key><true/>
  <key>NSRemindersUsageDescription</key>
  <string>YoyoSync reads your Reminders to update the YOYOBUILDS productivity dashboard.</string>
  <key>NSRemindersFullAccessUsageDescription</key>
  <string>YoyoSync reads your Reminders to update the YOYOBUILDS productivity dashboard.</string>
</dict>
</plist>
PLIST
codesign --force -s - "$DIR/YoyoSync.app"

echo "── Installing launchd agent (hourly 12:00–24:00)…"
PLIST=~/Library/LaunchAgents/com.yoyobuilds.dashboard.plist
mkdir -p ~/Library/LaunchAgents
cp "$DIR/com.yoyobuilds.dashboard.plist" "$PLIST"
launchctl bootout "gui/$(id -u)/com.yoyobuilds.dashboard" 2>/dev/null || true
launchctl bootstrap "gui/$(id -u)" "$PLIST"

echo "── Done. Trigger a first run (approve the Reminders prompt if asked):"
echo "   launchctl kickstart gui/\$(id -u)/com.yoyobuilds.dashboard"
