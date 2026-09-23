#!/usr/bin/env python3
"""
One command to read the Zeekr runtime secrets and print them ready for Home Assistant.

Prerequisites (see ../QUICKSTART.md):
  - a ROOTED Android device or emulator, arm64
  - frida-server 16.x running on it as root
  - the Zeekr app installed and *** LOGGED IN *** (values don't exist before login)
  - on this computer:  pip install "frida-tools==16.7.19"   (16.x, NOT 17)

Usage:
  python3 extract_runtime_keys.py                # auto-pick the USB device
  python3 extract_runtime_keys.py <device-id>    # e.g. emulator-5554 or 10.0.0.5:5555
"""
import sys
import time

try:
    import frida
except ImportError:
    sys.exit("frida not installed. Run:  pip install \"frida-tools==16.7.19\"")

PKG = "com.zeekr.overseas"
APP_LABEL = "ZEEKR"  # how the process shows up to frida


def get_device():
    if len(sys.argv) > 1:
        return frida.get_device(sys.argv[1], timeout=10)
    return frida.get_usb_device(timeout=10)


def find_pid(dev):
    for p in dev.enumerate_processes():
        if p.name == APP_LABEL or PKG in p.name:
            return p.pid
    return None


def main():
    try:
        dev = get_device()
    except Exception as e:
        sys.exit(f"Could not reach the device: {e}\n"
                 f"Is frida-server running on it? Try: frida-ps -U")

    pid = find_pid(dev)
    if pid is None:
        sys.exit("The Zeekr app isn't running. Open it and LOG IN, then re-run this.")

    with open("dump.js", "r", encoding="utf-8") as f:
        source = f.read()

    session = dev.attach(pid)
    script = session.create_script(source)
    result = {}

    def on_message(message, data):
        if message.get("type") == "send":
            result.update(message.get("payload", {}))
        elif message.get("type") == "error":
            print("script error:", message.get("stack", message), file=sys.stderr)

    script.on("message", on_message)
    script.load()
    time.sleep(3)

    ps = result.get("prod_secret", "")
    if not ps or len(str(ps)) < 8 or str(ps).startswith("<"):
        print("\nCouldn't read the values automatically.", file=sys.stderr)
        print("Most common cause: you haven't LOGGED IN to the app yet. Log in, then re-run.",
              file=sys.stderr)
        if result.get("_getterError"):
            print("getter error:", result["_getterError"], file=sys.stderr)
        print("If your app version differs, use the blob fallback in dump.js "
              "(see QUICKSTART.md).", file=sys.stderr)
        sys.exit(1)

    print("\nGot them (method: %s)\n" % result.get("_method", "?"))
    print("Paste these three into the Home Assistant zeekr_ev form:\n")
    print(f"  prod_secret : {result['prod_secret']}")
    print(f"  vin_key     : {result['vin_key']}")
    print(f"  vin_iv      : {result['vin_iv']}")
    print("\nThe other three (hmac_access_key, hmac_secret_key, password_public_key)")
    print("come from wysie/zeekr_key_extractor  (run with --region EU). See QUICKSTART.md.")
    print("\nDon't share these values publicly — they're app-global; everyone extracts their own.")


if __name__ == "__main__":
    main()
