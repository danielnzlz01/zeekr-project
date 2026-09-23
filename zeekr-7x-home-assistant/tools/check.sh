#!/usr/bin/env bash
# Quick prerequisite check before extracting.  Run:  bash check.sh
set -u
ok(){ echo "  OK   $1"; }
bad(){ echo "  MISS $1"; }

echo "Checking prerequisites..."

if command -v frida >/dev/null 2>&1; then
  v=$(frida --version 2>/dev/null)
  case "$v" in
    16.*) ok "frida $v (16.x - good)";;
    1[789].*|2*.*) bad "frida $v - TOO NEW. Use 16.x:  pip install \"frida-tools==16.7.19\"";;
    *) bad "frida $v - unexpected; want 16.x";;
  esac
else
  bad "frida not installed:  pip install \"frida-tools==16.7.19\""
fi

if command -v adb >/dev/null 2>&1; then
  dev=$(adb devices | awk 'NR>1 && $2=="device"{print $1}' | head -1)
  if [ -n "$dev" ]; then ok "adb device: $dev"; else bad "no adb device (connect / enable USB debugging)"; fi
else
  bad "adb not found (install platform-tools)"
fi

if command -v frida-ps >/dev/null 2>&1 && frida-ps -U 2>/dev/null | grep -qi 'ZEEKR'; then
  ok "Zeekr app is running (make sure you've LOGGED IN)"
else
  bad "Zeekr app not seen - open it, log in, and run frida-server (16.x) as root on the device"
fi

echo "Done. If everything says OK (and you've logged in), run:  python3 extract_runtime_keys.py"
