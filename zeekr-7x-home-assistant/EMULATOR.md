# Setting up a rooted Android emulator

No spare phone? You can do the whole extraction on a **rooted emulator** on your
computer. Read this once, then come back to [QUICKSTART.md](QUICKSTART.md) Step 3.

## Which emulator (this matters)

The Zeekr app's crypto lives in an **arm64 native library**. How well an emulator
runs it depends on your computer:

- **Apple Silicon Mac, or an arm64 Linux box → the reliable path.** An **arm64**
  Android Studio emulator runs the app *natively* (no translation), so the crypto
  lib just works, and it's fast.
- **Intel/AMD PC → works, but with a caveat.** You run an **x86_64** emulator that
  *translates* arm64 code. Most of the app runs fine, but the white-box crypto lib
  is exactly the kind of thing translation sometimes chokes on. Try it, if the app
  crashes on login, fall back to a physical arm phone.

### Which system image — and do I need Google Play?

Use a **"Google APIs"** image. This is the important bit:

- **Google APIs** — includes the Google Play **Services** framework (which the
  Zeekr app may rely on) but **not** the Play **Store**, and it **can be rooted**.
  This is the one you want.
- **Google Play** — has the Store, but ships with verified boot locked down, so it
  **cannot be rooted**. Avoid it.
- **AOSP / no-Google** — rootable, but has no Play Services; only use it if the app
  turns out not to need them.

You don't need the Play *Store* at all — you sideload the Zeekr APKs with `adb`
(Step 4), so a Google APIs image (Play Services present, rootable) is the sweet
spot. Pick API 33 or 34.

## 1. Create the AVD

1. Install **Android Studio**. Open **Device Manager → Create device**.
2. Pick a phone (e.g. Pixel 6), then a system image:
   - Apple Silicon / arm64 host: an **arm64-v8a**, API 33/34, **Google APIs** image.
   - Intel/AMD PC: an **x86_64**, API 33/34, **Google APIs** image.
3. Finish and launch it once so it boots.

## 2. Root it with Magisk (rootAVD)

[`rootAVD`](https://github.com/newbit1/rootAVD) patches the AVD's boot image with
Magisk:

```
git clone https://github.com/newbit1/rootAVD
cd rootAVD
./rootAVD.sh ListAllAVDs        # copy the exact path it prints for your AVD
./rootAVD.sh <that/ramdisk.img path>
```

It reboots the emulator with Magisk installed. Open the **Magisk** app to confirm
root. (`adb root` alone is *not* enough, Frida needs the Magisk su.)

## 3. Frida-server on the emulator

Use the `frida-server` build that matches the **emulator's ABI** (arm64 on an
arm64 AVD, x86_64 on an x86_64 AVD), version **16.7.19** to match your
`frida-tools`:

```
# download frida-server-16.7.19-android-<arch>.xz from frida's GitHub releases, unpack, then:
adb push frida-server-16.7.19-android-<arch> /data/local/tmp/frida-server
adb shell "su -c 'chmod 755 /data/local/tmp/frida-server && /data/local/tmp/frida-server &'"
frida-ps -U          # should list processes -> frida is working
```

## 4. Install the Zeekr app

Get the split APKs for `com.zeekr.overseas` — download a current **v3.0.x** from
[APKPure](https://apkpure.com/zeekr/com.zeekr.overseas) (any copy of a version is
identical; you don't need a specific phone's). It downloads as an `.xapk`, which
is a zip — unzip it to get `base.apk`, `split_config.arm64_v8a.apk`,
`split_config.xxhdpi.apk`, then install them together:

```
adb install-multiple base.apk split_config.arm64_v8a.apk split_config.xxhdpi.apk
```

Open it, accept the setup screens, and **log in with your second account**.

## 5. Extract

Now you're exactly where [QUICKSTART.md](QUICKSTART.md) Step 3 begins:

```
cd tools
bash check.sh                      # confirms frida + device + app-running
python3 extract_runtime_keys.py    # prints your three runtime keys
```

## If the app crashes or the values come out empty on x86

That's the arm64-translation caveat biting. Options, in order of reliability:
1. Run the emulator on an **arm64 host** (Apple Silicon / arm64 Linux) instead.
2. Use a **physical rooted arm phone** (a cheap second-hand one is plenty).

The extraction is one-time either way, once the six values are in Home Assistant,
you never need the rooted device again.

## Resources

- Android Studio emulator (install, create & run AVDs): https://developer.android.com/studio/run/emulator
- Managing AVDs (system images, Google APIs vs Play): https://developer.android.com/studio/run/managing-avds
- rootAVD — root an AVD with Magisk: https://github.com/newbit1/rootAVD
- Frida on Android (frida-server setup): https://frida.re/docs/android/
- Frida releases (download `frida-server` 16.7.19 for your ABI): https://github.com/frida/frida/releases
