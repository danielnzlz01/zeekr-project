# Quickstart: get your Zeekr into Home Assistant

A step-by-step for **non-experts**. If you can install an app, run a couple of
copy-paste commands, and edit a Home Assistant integration form, you can do this.
Budget ~30–45 minutes the first time.

> This reads **your own** car's data into **your own** Home Assistant, the same
> access the official Zeekr app has. Don't use it on cars you don't own, and
> don't share the extracted key values — they're app-global constants, so
> everyone extracts their own (it's quick).

> **Two shortcuts before you start:**
> - **No spare phone?** A rooted Android **emulator** works — full setup, links,
>   and the Google-image question are in **[EMULATOR.md](EMULATOR.md)**.
> - **Want an AI to drive it?** Hand **[AI_INSTRUCTIONS.md](AI_INSTRUCTIONS.md)**
>   to Claude Code (or any capable coding agent that has shell + `adb` access) and
>   it will set up the environment and walk you through the whole extraction, step
>   by step.

---

## What you're collecting

The `Fryyyyy/zeekr_homeassistant` integration asks for **6 values**. Three you get
statically, three you get at runtime:

| Value | Where it comes from |
|---|---|
| `hmac_access_key` | **static** — [`wysie/zeekr_key_extractor`](https://github.com/wysie/zeekr_key_extractor) (run with `--region EU`) |
| `hmac_secret_key` | **static** — same tool |
| `password_public_key` | **static** — same tool |
| `prod_secret` | **runtime** — this repo's `tools/` (see Step 3) |
| `vin_key` | **runtime** — this repo's `tools/` |
| `vin_iv` | **runtime** — this repo's `tools/` |

Why two methods? The three static keys are plain constants in the app. The other
three are **encrypted inside the app and only decrypted while it runs** (iWall /
`libiwallca.so`), so no static tool can read them — you dump them live. Full
technical story in [README.md](README.md).

---

## What you need

- A **rooted Android phone or emulator** (Magisk is fine), arm64. A cheap
  second-hand phone or an Android emulator both work. *(A non-rooted phone can't
  do this — Frida needs root.)*
- The **Zeekr app** (`com.zeekr.overseas`), a **current v3.0.x** build. You do
  **not** need to pull it off any particular phone — a given version is the same
  APK everywhere. Download it from **[APKPure](https://apkpure.com/zeekr/com.zeekr.overseas)**
  (it comes as an `.xapk`, which is just a zip of the split APKs — unzip it, then
  `adb install-multiple base.apk split_config.arm64_v8a.apk split_config.xxhdpi.apk`).
  Use a recent v3.0.x, the runtime tool targets that build's internals and the EU
  gateway accepts current versions.
- A **computer** with Python and `adb`.
- **Frida 16.x** — *not 17* (v17 removed the Java bridge and this fails):
  ```
  pip install "frida-tools==16.7.19"
  ```
  and the matching **`frida-server` 16.7.19 (arm64)** pushed to the device and
  running as root (see [Frida's docs](https://frida.re/docs/android/)).
- A **second Zeekr account** with the car **shared to it**. Use this account for
  Home Assistant so it doesn't log your own phone's app out.

> **Do I really need a rooted phone? Yes** — there's no way around it. The three
> runtime keys only exist *inside the running app's memory*, and reading them
> needs Frida, which needs root. The good news: it's a **one-time** job. Once the
> six values are in Home Assistant, the rooted device is never needed again, HA
> talks to Zeekr's cloud directly. You do **not** need to root your everyday
> phone: a cheap second-hand Android or a **rooted emulator** works (full emulator
> setup in **[EMULATOR.md](EMULATOR.md)**). One catch:
> the app's crypto is an **arm64** native library, so an x86 emulator needs arm
> translation (use an arm64 system image, or just use a physical arm phone).

---

## Step 1 — second account + share the car

In the Zeekr app on your normal phone, create/invite a second account and share
the vehicle to it. You'll log in as this second account on the rooted device.

## Step 2 — the three static keys

Get the app's APKs (from [APKPure](https://apkpure.com/zeekr/com.zeekr.overseas) —
see "What you need" above; unzip the `.xapk` to get `base` / `split_config.arm64_v8a`
/ `split_config.xxhdpi`) and run the static extractor against them:

```
git clone https://github.com/wysie/zeekr_key_extractor
cd zeekr_key_extractor
# follow its README to point it at those base + arm64 + xxhdpi APKs
python3 extractor.py --region EU
```

Write down `hmac_access_key`, `hmac_secret_key`, `password_public_key`.
`X-APP-ID` = `ZEEKRCNCH001M0001` is **correct for EU** (the "CN" is a red
herring), don't change it.

## Step 3 — the three runtime keys (the easy way)

1. On the rooted device, start `frida-server` (16.x) as root.
2. Open the Zeekr app and **log in with the second account**. This matters: the
   encryption only wakes up on the first signed request, so you must log in — not
   just open the app.
3. On your computer, from this repo's `tools/` folder:
   ```
   cd tools
   python3 extract_runtime_keys.py
   ```
   It finds the running app, reads the three decrypted values, and prints a block
   you can paste straight into Home Assistant. If it prints them, **you're done
   with extraction — you never had to touch jadx or copy any blobs.**

If it says the getter method didn't work on your app version, see
[*If your app version is different*](#if-your-app-version-is-different) below.

## Step 4 — install the integration + configure

Install `Fryyyyy/zeekr_homeassistant` via HACS. The stock PyPI `zeekr_ev_api`
signs requests correctly, so you do **not** need "Use local API", it's optional.

Then fill the `zeekr_ev` form with:

- **Username / password:** the second account.
- **Country code:** e.g. `SE`. **Drive side:** `lhd`.
- `hmac_access_key`, `hmac_secret_key`, `password_public_key`: from Step 2.
- `prod_secret`, `vin_key`, `vin_iv`: from Step 3.
- **Use local API:** optional — off is fine; turn it on only if you want `main`'s
  newer relogin fix.

## Step 5 — verify

`sensor.zeekr_api_status` should read **Connected** and vehicle entities (battery,
range, locks, tyres, location…) appear. Press the "poll" button; if the car is
asleep it may take a moment.

## Cleanup

- Uninstall the app from the extraction device, or the second account ends up
  logged in twice and the sessions fight (HA should own it).
- Stop/remove `frida-server`.

---

## Troubleshooting

| Symptom | Meaning / fix |
|---|---|
| `Java is not defined` | You're on Frida 17. Use 16.x (`pip install "frida-tools==16.7.19"` + matching frida-server). |
| Script prints empty / null values | You didn't **log in** before running it, or the app was only opened. Log in, then re-run. |
| `Invalid access key` (`0001`) | Wrong HMAC keys or region — re-run the static extractor with `--region EU`. |
| `9300` at login | Country/region vs key mismatch. |
| `Signature authentication failed` (`079025`) at login | Wrong `prod_secret` — it's runtime-only on 3.0.x, so the static candidates fail. Re-dump it (Step 3). |
| `Decrypt X-VIN failed` (`079025`) at vehicle status | Wrong `vin_key`/`vin_iv`. The old-APK VIN keys are **not** accepted on the EU 7X — you must use the runtime ones from Step 3. |
| App not found by the script | It shows up to Frida as **`ZEEKR`**; make sure it's open and logged in. |

## If your app version is different

The runtime method reads values out of specific (obfuscated) classes that are
correct for `com.zeekr.overseas` v3.0.x. If Zeekr ships a new build and the
class/method names move, the "easy" getter path may fail and you fall back to the
blob method:

1. `jadx` the base APK and open `xn/a.java`; copy the three base64 strings for
   fields `c` (prod_secret), `a` (vin_key), `l` (vin_iv).
2. Paste them into `tools/dump.js` (the `PROD` / `VKEY` / `VIV` placeholders).
3. Re-run `python3 extract_runtime_keys.py`.

If even that moves, the anchor is the App-Signature signer: find where
`X-SIGNATURE` is built, follow the HMAC **key** back to a runtime decrypt call
(`SecuritySuite`), and hook that. The [README](README.md) walks the v3.0.6 chain.
```
