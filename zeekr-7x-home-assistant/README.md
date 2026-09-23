# Connecting a Zeekr 7X (EU) to Home Assistant — the complete, working method

*Owner-access write-up: reading your own vehicle's data into your own Home
Assistant, using the community `Fryyyyy/zeekr_homeassistant` integration. This
documents the two problems that make EU 7X logins fail with error
`079025`, and how to solve both. It describes the **method**; you extract
your **own** keys from your **own** app — no secret values are published here.*

Tested: Zeekr 7X, Sweden, app `com.zeekr.overseas` v3.0.6, EU gateway
`eu-snc-tsp-api-gw.zeekrlife.com`, integration `zeekr_ev` + `zeekr_ev_api`.
Result: full login and 93 entities (battery, range, climate, locks, doors, tyre
pressures, location).

---

> **New to this? Start with [QUICKSTART.md](QUICKSTART.md)** — a plain,
> step-by-step walkthrough with a one-command tool. This README is the
> technical deep-dive into *why* it works.
> Prefer to have an AI do the heavy lifting? Hand
> [AI_INSTRUCTIONS.md](AI_INSTRUCTIONS.md) to Claude Code (or any capable
> coding agent with shell + `adb` access) and it will set up the environment
> and walk you through the extraction step by step.

## The pieces — what all these repos and tools are

Getting the car into Home Assistant involves a few separate projects. Here's the
map so the rest of this makes sense:

| Piece | What it is | Its role here |
|---|---|---|
| **[`Fryyyyy/zeekr_homeassistant`](https://github.com/Fryyyyy/zeekr_homeassistant)** | The Home Assistant custom integration (`custom_components/zeekr_ev`), installed via HACS | The thing you add to HA; it logs in to Zeekr's cloud and creates the car entities. It's the form that asks for the 6 keys. |
| **`zeekr_ev_api`** | The Python client library the integration uses to sign and send requests to Zeekr | Installed automatically with the integration. Its **PyPI build signs correctly** (byte-identical to `main`); the optional **`use_local_api`** switch just runs `main`, which carries a later relogin fix — handy but not required for login. |
| **[`wysie/zeekr_key_extractor`](https://github.com/wysie/zeekr_key_extractor)** | A tool that pulls keys out of the Zeekr Android app **statically** (from the APK) | Gives you **3 of the 6** keys: `hmac_access_key`, `hmac_secret_key`, `password_public_key` (run it with `--region EU`). |
| **This repo** | The method + a small **Frida** tool | Gets the **other 3** keys — `prod_secret`, `vin_key`, `vin_iv` — which *cannot* be extracted statically, and explains the whole failure chain. |
| **The Zeekr app** (`com.zeekr.overseas`) | The official Android app | Where all 6 keys live; you extract them from **your own** copy. |
| **HACS** | Home Assistant Community Store | How you install the `zeekr_ev` integration into HA. |

So the job is: collect **6 keys** (3 static from `zeekr_key_extractor`, 3 runtime
from here). The rest of this document explains *why* the runtime three are needed
and how each `079025` failure maps to a cause. For the click-by-click, see
**[QUICKSTART.md](QUICKSTART.md)**.

## TL;DR

EU 7X on v3.0.x fails at two points, both masked as `079025`, and both are about
the last three keys:

1. **`prod_secret` cannot be extracted statically.** It is an iWall ECIES blob
   decrypted at runtime, so the static extractor's candidates never work. Dump
   the real value with Frida after logging in. (Surfaces as *"Signature
   authentication failed"* at login.)
2. **`vin_key` / `vin_iv` also cannot be extracted statically**, and the old-APK
   values that older docs suggest are **not** accepted by the EU gateway. Dump
   the real ones the same way. (Surfaces as *"Decrypt X-VIN failed"* at the
   vehicle-status call.)

The request **signing itself is fine** — the stock PyPI `zeekr_ev_api` build signs
correctly (byte-identical to `main`), so `use_local_api` is **optional**, not a
fix. `X-APP-ID` (`ZEEKRCNCH001M0001`) is **correct** for EU — the app selects it
by brand, not region, so the "CN" is a red herring. Don't chase it.

---

## Background: what actually signs the requests

The App-Signature (`X-SIGNATURE`) is HMAC-SHA256 over a base string built from a
fixed allowlist of headers (sorted), the query, an MD5 of the JSON body, the
HTTP method, and the path. The signing **key** is not a static string — the app
derives it at runtime:

```
X-SIGNATURE key = m.a.k()                       (class com.zeekr.snc.log.m)
                = ko.l.e(app, PRODUCT)
                = yn.a.c(EnvType.PRODUCT, xn.a.c)   // decrypt an iWall ECIES blob
```

`yn.a.c()` decrypts via `SecuritySuite.r()` (iWall white-box, `libiwallca.so`)
using an EC private key that only exists in the native lib at runtime. So the
signing secret (`prod_secret`), and likewise the VIN AES key/iv, cannot be read
out of the APK statically — the static extractor returns heuristic candidates
that never match.

Field map in `com.zeekr.snc.log.m` (getters → static fields), for reference:

| value | getter | field | source |
|---|---|---|---|
| prod_secret | `k()` | `m` | `ko.l.e` = decrypt `xn.a.c` |
| vin_key | `j()` | `l` | `ko.l.d` = decrypt `xn.a.a` |
| vin_iv | `c()` | `n` | `ko.l.b` = decrypt `xn.a.l` |

`X-VIN` is `AES-128-CBC(VIN, vin_key, vin_iv)` via `ko.a.f`.

---

## Prerequisites

- A **rooted** Android device or emulator (Magisk is fine), arm64.
- The **same app version your account uses**, installed on that device. Pull the
  split APKs from a phone that has it and `adb install-multiple base + arm64 +
  xxhdpi`.
- **Frida 16.x** on both host and device. **Not 17** — Frida 17 removed the
  built-in Java bridge and you'll get `Java is not defined`. This project used
  `frida`/`frida-tools` 16.7.19 and matching `frida-server` arm64.
- `jadx` to decompile, so you can read the two base64 blobs from your APK.
- A second Zeekr account with the car **shared to it**, used only by HA (so the
  integration doesn't log your main phone app out).

---

## Step 1 — install the integration

Install `Fryyyyy/zeekr_homeassistant` via HACS as normal. The signing code in the
current PyPI `zeekr_ev_api` build (`0.1.14`) is **correct** — byte-identical to
`main` — so you do **not** need `use_local_api` for the request signature to be
right. (`main` does carry a small later relogin / stale-auth-header fix in
`client.py`; running it via `use_local_api` is a reasonable optional upgrade, but
it is not what makes login succeed — the six keys are.)

---

## Step 2 — extract the real secrets at runtime (both causes)

1. Read the three encrypted blobs from your APK with jadx: `xn.a.c` (prod_secret),
   `xn.a.a` (vin_key), `xn.a.l` (vin_iv) — full base64 strings in `xn/a.java`.
2. Push and start `frida-server` (16.x) as root on the device.
3. Launch the app and **log in with the target account**. The iWall SDK only
   initializes on the first signed call, so a login is required — just opening
   the app leaves `SecuritySuite.D()` false and the decryptor returns null.
4. The decryptor caches decrypted values and checks the cache first, so after
   login the values are in memory. Attach (by **PID** — `frida-ps` shows the
   process as `ZEEKR`, not the package name) and call the decryptor with each
   blob:

```js
// frida script — run after login
Java.perform(function () {
  var YA = Java.use('yn.a');
  var inst = YA.$new();                 // static YA.a.value may be null; $new works
  var EnvType = Java.use('com.geely.snc.security.api.model.EnvType');
  var P = EnvType.PRODUCT.value;
  var PROD = '<xn.a.c base64 from your APK>';
  var VKEY = '<xn.a.a base64 from your APK>';
  var VIV  = '<xn.a.l base64 from your APK>';
  send({
    prod_secret: inst.c(P, PROD),   // 32 hex chars
    vin_key:     inst.c(P, VKEY),   // 16 chars
    vin_iv:      inst.c(P, VIV),    // 16 chars
  });
});
```

Python driver:

```python
import frida, time
dev = frida.get_device('<device-id>', timeout=10)          # e.g. 'emulator-5554' or 'ip:port'
pid = int(open('app.pid').read())                          # adb shell pidof com.zeekr.overseas
s = dev.attach(pid)
sc = s.create_script(open('dump.js').read())
sc.on('message', lambda m, d: print(m.get('payload')))
sc.load(); time.sleep(4)
```

The other four values (`hmac_access_key`, `hmac_secret_key`,
`password_public_key`, plus `prod_secret` cross-check) come from the static
`wysie/zeekr_key_extractor` run with `--region EU` — those are correct. Only the
three runtime values above need Frida.

---

## Step 3 — configure the integration

In the `zeekr_ev` config form:

- Username / password: the **second** account.
- Country code: your country (e.g. `SE`). Drive side: `lhd`.
- `hmac_access_key`, `hmac_secret_key`, `password_public_key`: from the static
  extractor (`--region EU`).
- `prod_secret`, `vin_key`, `vin_iv`: the **runtime** values from Step 2.
- **Use local API:** optional — leave it off (stock signing is correct); turn it
  on only if you want `main`'s newer relogin fix.

Login should succeed. If vehicle status then fails with
`Decrypt X-VIN failed`, your `vin_key`/`vin_iv` are still the wrong (static)
ones — replace them with the runtime values.

---

## Cleanup

- Uninstall the app from the extraction device, or the second account is logged
  in on two sessions (device + HA) and they log each other out. HA should own
  the session.
- Stop and remove `frida-server`.

---

## What each `079025` variant means (debugging map)

| Response | Stage | Meaning |
|---|---|---|
| `Invalid access key` (0001) | URL fetch | wrong HMAC keys or wrong region |
| `9300` | `_do_login_request` | country/region vs key mismatch |
| `Signature authentication failed` (079025) | `_bearer_login` | `prod_secret` wrong — it's runtime-only on 3.0.x, the static candidates never work |
| `Decrypt X-VIN failed` (079025) | vehicle status | wrong `vin_key`/`vin_iv` — the old-APK values are rejected on 3.0.x EU |

---

## Responsible use

This accesses **your own** vehicle's telemetry with **your own** account, the
same thing the Zeekr app does. Don't publish decrypted secret values — they are
app-global constants and publishing them helps circumvention. Extract your own.
Don't use it to access vehicles you don't own.
