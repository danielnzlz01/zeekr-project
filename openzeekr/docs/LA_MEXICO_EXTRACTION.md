# Adding LA (Mexico) Support to OpenZeekr — Extraction Walkthrough

This is a **do-it-yourself extraction guide**. You run every step here against **your own**
Mexico Zeekr account, app, and car, on a **rooted Android phone**. Nothing in this file is a
secret — it is only instructions plus blank placeholders. When you are done, fill in the
[Results template](#8-results-template--paste-this-back) at the bottom and hand it back, and the
values get wired into the app (`secrets.properties`, `Region.kt`, README).

> ⚠️ **Authorized use only.** Do this only with an account and vehicle you own or are explicitly
> authorized to access. Do not publish the extracted values — they are app-global constants;
> everyone extracts their own.

---

## 0. TL;DR of the whole job

1. Root your arm64 Android phone and set up adb.
2. Install the Mexico Zeekr app and log in **once** with a shared secondary account.
3. Pull the APKs and run the **static** extractor (`--region EM`) → 3 keys.
4. Run **Frida** against the live app → runtime keys (prod secret, VIN key/IV, overseas AK/SK, inbox secret).
5. **Confirm the LA gateway hosts** by watching the app's real traffic.
6. Fill in the results template and send it back.

We are collecting **all** values (nothing optional), so the digital key, notifications inbox, and
push all work on Mexico, not just login/control/status. Budget ~60–90 minutes the first time. The
rooted phone is only needed for this one-time job.

---

## 1. What we're collecting and why

OpenZeekr needs a full set of values for a region: the **6 core secrets**, the **xchanger** and
**overseas/inbox** secrets, and the **gateway hosts** for Mexico. All are required.

### 1a. All secrets → where each goes in `secrets.properties`

| Secret | `secrets.properties` key | Group | How you get it |
|---|---|---|---|
| HMAC access key | `EM_HMAC_ACCESS_KEY` | region-specific (LA = EM set) | static extractor `--region EM` (Step 4) |
| HMAC secret key | `EM_HMAC_SECRET_KEY` | region-specific (LA = EM set) | static extractor `--region EM` (Step 4) |
| Prod secret (X-SIGNATURE key) | `EM_PROD_SECRET` | region-specific (LA = EM set) | Frida runtime dump (Step 5) |
| Password public key (RSA) | `PASSWORD_PUBLIC_KEY` | shared across regions | static extractor (Step 4) |
| VIN AES key | `VIN_KEY` | shared across regions | Frida runtime dump (Step 5) |
| VIN AES IV | `VIN_IV` | shared across regions | Frida runtime dump (Step 5) |
| xchanger sign secret (BLE digital key) | `XCHANGER_SIGN_SECRET` | region-specific | **same value as `EM_PROD_SECRET`** (Step 6) |
| Overseas access key (inbox/push) | `OVERSEAS_ACCESS_KEY` | shared | Frida hook of `libenv.so` getters (Step 6) |
| Overseas secret key (inbox/push) | `OVERSEAS_SECRET_KEY` | shared | Frida hook of `libenv.so` getters (Step 6) |
| Inbox auth secret (HS256) | `INBOX_AUTH_SECRET` | shared | Frida runtime dump (Step 6) |

**Why LA uses the "EM" set.** In `openzeekr/core/src/main/java/com/openzeekr/app/net/Region.kt`,
`Region.LA` has `extractorRegion = "EM"`. The stock native lib only distinguishes **EU / EM / SEA**
for signing secrets; "EM" (Emerging Markets) is an umbrella covering LA, ME and others. So the three
region-specific signing keys for Mexico are the **EM** keys, while `PASSWORD_PUBLIC_KEY`, `VIN_KEY`
and `VIN_IV` are shared. When you pick region **LA** in the app, `ConfigStore.setRegion` swaps in
the `EM_*` signing keys and keeps the shared values.

> This is exactly the mechanism that made SEA work in 0.1.4: without the region's own signing keys,
> the app fell back to the EU keys and the gateway rejected the login.

### 1b. Hosts to confirm for `Region.LA`

Only EU is verified today; LA was reconstructed from the stock host tables and some fields are
best-effort guesses. Confirm each against real traffic (Step 7):

| `Region.LA` field | Current value in `Region.kt` | Confidence |
|---|---|---|
| `tspBaseUrl` | `https://la-snc-tsp-api-gw.zeekrlife.com` | likely |
| `azureHost` | `https://gateway-pub-hw-em-mx.zeekrlife.com` | likely |
| `xchangerHost` | `https://api-zk.ecloudus.com` | **guess — most likely to be wrong** |
| `projectId` | `ZEEKR_LA` | likely |
| `countryCode` | `MX` | likely |
| `snsRegion` | `us-east-1` | best-effort |

---

## 2. Environment — rooted arm64 Android phone

You need a phone where you can run **Frida as root** against an **arm64** build of the app (the
crypto lives in an arm64 native lib, `libiwallca.so`). A physical arm64 phone is the reliable path —
the app's arm64 native libs run natively, so Frida attaches cleanly.

- Use a spare/second-hand arm64 phone rooted with **Magisk**. Rooting (bootloader unlock) wipes the
  device — don't use your daily driver if you can avoid it.
- The rooted phone is only needed for this one-time extraction; afterward the app runs normally.

### 2a. Prep

1. **Enable adb.** Developer Options → USB debugging. Verify from the host:
   ```bash
   adb devices
   ```
2. **Secondary account + shared car.** In the Zeekr app on your normal phone, create/invite a
   **second account** and **share your car** to it. You'll log into the rooted phone with this
   second account, so extraction/testing doesn't keep logging your main app out (Zeekr allows one
   active session per account).
3. **Install the Mexico app** on the rooted phone (see Step 3).

---

## 3. Get the app + pull the APKs

> **Package name matters.** Zeekr ships under different package names per market:
> - **EU:** `com.zeekr.overseas`
> - **Most non-EU/non-CN markets (incl. Emerging Markets / Mexico):** `com.zeekr.global`
>
> Mexico is EM, so your app is **most likely `com.zeekr.global`**. Confirm which one your MX account
> actually uses before proceeding — the rest of the commands take the package as a variable.

Find which package is installed:
```bash
adb shell pm list packages | findstr zeekr
```
Set it once for the session (PowerShell):
```powershell
$PKG = "com.zeekr.global"   # or "com.zeekr.overseas" if that's what your MX account uses
```

Install the app if needed. Easiest source is APKPure (comes as an `.xapk`, which is a zip of the
split APKs). Unzip it, then install all splits together:
```bash
adb install-multiple base.apk split_config.arm64_v8a.apk split_config.xxhdpi.apk
```

Open the app and **log in with the secondary MX account at least once** (this matters for Step 5).

Now pull the APKs you'll feed to the static extractor:
```powershell
adb shell pm path $PKG
```
That prints something like:
```
package:/data/app/~~aaaa==/com.zeekr.global-bbbb==/base.apk
package:/data/app/~~aaaa==/com.zeekr.global-bbbb==/split_config.arm64_v8a.apk
package:/data/app/~~aaaa==/com.zeekr.global-bbbb==/split_config.xxhdpi.apk
```
Pull the **base** and the **arm64** split (the xxhdpi one isn't needed):
```bash
adb pull /data/app/~~aaaa==/com.zeekr.global-bbbb==/base.apk zeekr_base.apk
adb pull /data/app/~~aaaa==/com.zeekr.global-bbbb==/split_config.arm64_v8a.apk zeekr_arm64.apk
```
(Substitute the exact paths from your own `pm path` output.)

---

## 4. Static keys — `zeekr_key_extractor --region EM`

This gives you 3 of the values: `hmac_access_key`, `hmac_secret_key`, `password_public_key`.
(It may also print `prod_secret` / `vin_key` / `vin_iv` on **older** APKs — see the note below.)

From the workspace root (`c:\Users\RH753JV\Documents\openzeekr`):
```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r zeekr_key_extractor\requirements.txt
python zeekr_key_extractor\zeekr_extract_secrets.py zeekr_base.apk zeekr_arm64.apk --region EM
```

Expected tail of the output:
```
      [OK] Password Public Key (216 chars)
      [OK] Prod Secret: ********************************
      ...
      [OK] HMAC Access Key: ********************************
      [OK] HMAC Secret Key: ****************************************

  All 6 secrets extracted successfully!
  Secrets saved to: zeekr_secrets.json
```
It writes `zeekr_secrets.json` next to the APKs. From it, record:
- `hmac_access_key`  → `EM_HMAC_ACCESS_KEY`
- `hmac_secret_key`  → `EM_HMAC_SECRET_KEY`
- `password_public_key` → `PASSWORD_PUBLIC_KEY`

> **`--region EM` is correct for Mexico.** The region flag only changes the two HMAC keys; the other
> four secrets are identical across regions.

> **Which `prod_secret` / VIN values to trust.** On current app builds the extractor **cannot** read
> `prod_secret` / `vin_key` / `vin_iv` statically (they're behind iWall ECIES) — get those from
> Frida in Step 5. If you happen to run the extractor on an **old** APK and it prints them, treat
> them as a fallback only; the runtime values from Step 5 are authoritative for your app version.

---

## 5. Runtime keys — Frida + `dump.js`

This gives you `prod_secret`, `vin_key`, `vin_iv`.

### 5a. Install Frida **16.x** (NOT 17 — v17 removed the Java bridge and this fails)
On the host:
```powershell
pip install "frida-tools==16.7.19"
frida --version   # should print 16.x
```
Push the matching **`frida-server` 16.7.19 (arm64)** to the phone and run it as root. Download the
`frida-server-16.7.19-android-arm64` binary from Frida's GitHub releases, then:
```bash
adb push frida-server-16.7.19-android-arm64 /data/local/tmp/frida-server
adb shell "su -c 'chmod 755 /data/local/tmp/frida-server'"
adb shell "su -c '/data/local/tmp/frida-server &'"
```
Sanity check from the host — the app shows up to Frida as **`ZEEKR`**:
```bash
frida-ps -U | findstr /i ZEEKR
```

### 5b. Log in first, then dump
1. On the phone, make sure you are **logged into the app with the MX account** (the decryptor only
   initializes on the first signed request — merely opening the app leaves the values null).
2. Run the ready-made dumper from the mescon tools folder:
   ```powershell
   cd zeekr-7x-home-assistant\tools
   python extract_runtime_keys.py
   # or target a specific device: python extract_runtime_keys.py <device-id>
   ```
   On success it prints:
   ```
   Got them (method: getters)

     prod_secret : ................................
     vin_key     : ................
     vin_iv      : ................
   ```
   Record:
   - `prod_secret` (32 hex chars) → `EM_PROD_SECRET`
   - `vin_key` (16 chars) → `VIN_KEY`
   - `vin_iv` (16 chars) → `VIN_IV`

### 5c. If the automatic getters fail (different app version)
`dump.js` targets the obfuscated classes of `com.zeekr.overseas` v3.0.x. The Mexico
`com.zeekr.global` build may use **different class/field names**, so the "getters" method can fail.
Fall back to the blob method:
1. Decompile the base APK with **jadx** and open `xn/a.java`. Copy the three base64 strings for
   fields `c` (prod_secret), `a` (vin_key), `l` (vin_iv).
   - If `xn/a.java` doesn't exist / looks different on the global build, find where `X-SIGNATURE`
     is built and follow the HMAC **key** back to the runtime decrypt call (`SecuritySuite` /
     iWall), and note that class — that's the anchor to hook.
2. Paste the three blobs into the `PROD` / `VKEY` / `VIV` placeholders in
   `zeekr-7x-home-assistant\tools\dump.js` (Method B).
3. Re-run `python extract_runtime_keys.py`.

> If the class names moved and you can't locate the blobs, capture what you find (class names,
> any error text) in the results template and we'll adapt the hook.

---

## 6. The remaining secrets (xchanger, overseas AK/SK, inbox)

These complete the set so the digital key and the notifications inbox/push also work.

### 6a. `XCHANGER_SIGN_SECRET` — no extra work
Per the app's own signing code (`AccountLogin.hfSign` / `SecretsConfig`), the xchanger HF signing
key is the **same value as the prod secret** (`getSignSecret() == getTSPSecretValue(region,"ONLINE")
== prod_secret`). So:
- `XCHANGER_SIGN_SECRET` = the exact same string you recorded as `EM_PROD_SECRET` in Step 5.

Just copy it across; there's nothing else to capture.

### 6b. `OVERSEAS_ACCESS_KEY` / `OVERSEAS_SECRET_KEY` — hook `libenv.so` getters
These are the native `libenv.so` values `getNativeApplicationId()` (access key) and
`getNativeSecret()` (secret key), for the EM / PROD environment. Hook the Java wrappers with Frida.

Save this as `overseas_hook.js`:
```js
// overseas_hook.js — print the overseas-app AK/SK (getNativeApplicationId / getNativeSecret)
Java.perform(function () {
  var hits = 0;
  Java.enumerateLoadedClasses({
    onMatch: function (name) {
      try {
        if (name.indexOf('$') !== -1) return;
        var clazz = Java.use(name);
        var methods = clazz.class.getDeclaredMethods();
        methods.forEach(function (m) {
          var mn = m.getName();
          if (mn === 'getNativeApplicationId' || mn === 'getNativeSecret' || mn === 'getNativeHost') {
            try {
              var overloads = clazz[mn].overloads;
              overloads.forEach(function (ov) {
                ov.implementation = function () {
                  var r = ov.apply(this, arguments);
                  console.log('[' + name + '.' + mn + '] args=' + JSON.stringify(Array.prototype.slice.call(arguments)) + ' => ' + r);
                  hits++;
                  return r;
                };
              });
            } catch (e) {}
          }
        });
      } catch (e) {}
    },
    onComplete: function () { console.log('hooks installed; now trigger the inbox/notifications in the app'); }
  });
});
```
Run it and then open the **message inbox / notifications** in the app so the getters fire:
```bash
frida -U -l overseas_hook.js -n ZEEKR
```
You want the `getNativeApplicationId` return (→ `OVERSEAS_ACCESS_KEY`) and the `getNativeSecret`
return (→ `OVERSEAS_SECRET_KEY`). If several environment rows print, take the one whose
`getNativeHost` value is the Mexico gateway (`gateway-pub-hw-em-mx.zeekrlife.com`).

> Alternative: the static extractor's native analysis also resolves the `getNativeApplicationId /
> getNativeSecret / getNativeHost` tables. If the Frida hook is awkward, note the raw table rows the
> extractor prints and we can pick the EM/PROD row together.

### 6c. `INBOX_AUTH_SECRET` — hook the HS256 token signer
The inbox `Authorization` token is an HS256 JWT the app mints client-side; its signing secret is
string-obfuscated in the APK, so dump it at runtime. Hook the HMAC/JWT signing path:

Save this as `inbox_hook.js`:
```js
// inbox_hook.js — reveal the HS256 secret used to sign the inbox Authorization token
Java.perform(function () {
  // Most builds sign via javax.crypto.Mac with an HmacSHA256 SecretKeySpec.
  var SKS = Java.use('javax.crypto.spec.SecretKeySpec');
  SKS.$init.overload('[B', 'java.lang.String').implementation = function (keyBytes, algo) {
    try {
      if (('' + algo).toUpperCase().indexOf('HMACSHA256') !== -1) {
        var s = '';
        for (var i = 0; i < keyBytes.length; i++) s += String.fromCharCode(keyBytes[i] & 0xff);
        console.log('[HmacSHA256 key] len=' + keyBytes.length + ' utf8=' + s);
      }
    } catch (e) {}
    return this.$init(keyBytes, algo);
  };
});
```
Run it, then open the **inbox** in the app to trigger token minting:
```bash
frida -U -l inbox_hook.js -n ZEEKR
```
Several HmacSHA256 keys may print (the app signs other things too). The inbox secret is the one used
right when the inbox loads; if unsure, capture all candidates in the notes and we'll identify it by
which one produces a token the gateway accepts.

> This one is the fiddliest. If you can't isolate it, leave `INBOX_AUTH_SECRET` in the template with
> your candidate list — everything except the in-app inbox still works without it, and we can refine.

---

## 7. Verify the LA gateway hosts (proxy capture)

The signing keys are useless if the app is pointed at the wrong Mexico hosts. Confirm them by
watching the app's real traffic during a login.

### 7a. Set up an intercepting proxy
1. Install **mitmproxy** on the host (`pip install mitmproxy`) and run `mitmweb` (or `mitmproxy`).
2. Point the phone at it: set the Wi-Fi proxy to your host's IP + mitmproxy port (8080), then open
   `http://mitm.it` on the phone and install the mitmproxy **CA cert** (system cert if possible).
3. Open the Zeekr app and **log in** with the MX account, then open the car / pull to refresh so it
   fetches vehicle status, and open the inbox and trigger the digital-key/session flow so every host
   shows up.

### 7b. Record the real hosts and compare
Note every `*.zeekrlife.com` / `api-zk.*` / `*.ecloud*.com` host you see, and match them up:

| What to look for in traffic | Maps to `Region.LA` field | Current guess |
|---|---|---|
| `*-snc-tsp-api-gw.zeekrlife.com` (the bearer/X-SIGNATURE calls) | `tspBaseUrl` | `https://la-snc-tsp-api-gw.zeekrlife.com` |
| host serving `/zeekr-cuc-idaas/`, `/overseas-app/`, `/zom-message-core` | `azureHost` | `https://gateway-pub-hw-em-mx.zeekrlife.com` |
| `api-zk.<suffix>` on the DK **session/secure** call | `xchangerHost` | `https://api-zk.ecloudus.com` (**verify the suffix**) |
| `X-PROJECT-ID` header value on TSP calls | `projectId` | `ZEEKR_LA` |
| `country` / `registcountry` header on login | `countryCode` | `MX` |
| SNS region in the push-registration body/response (`arn:aws:sns:<region>:…`) | `snsRegion` | `us-east-1` |

Write down the **actual** value for each in the results template (and flag any that differ from the
guess above — especially `xchangerHost`).

---

## 8. Results template — paste this back

Fill in everything and send it back. **Do not post this publicly.**

```text
# --- Region: LA (Mexico) ---
# App package used: com.zeekr.global | com.zeekr.overseas   (circle one)
# App version:      __________

## Core secrets
EM_HMAC_ACCESS_KEY =
EM_HMAC_SECRET_KEY =
EM_PROD_SECRET     =
PASSWORD_PUBLIC_KEY=
VIN_KEY            =
VIN_IV             =

## Digital key + inbox/push
XCHANGER_SIGN_SECRET = (same as EM_PROD_SECRET)
OVERSEAS_ACCESS_KEY  =
OVERSEAS_SECRET_KEY  =
INBOX_AUTH_SECRET    =

## Confirmed hosts for Region.LA (write the REAL values you observed)
tspBaseUrl   =
azureHost    =
xchangerHost =
projectId    =
countryCode  =
snsRegion    =

## Notes (class names if getters failed, HmacSHA256 candidates for the inbox secret,
## hosts that differed from the guess, etc.)
-
```

---

## 9. Cleanup

- Stop and remove `frida-server`:
  ```bash
  adb shell "su -c 'pkill frida-server'"
  ```
- Uninstall the app from the extraction phone (or the second account ends up logged in twice and
  the sessions fight). The **phone app** should own the session on your main account; OpenZeekr uses
  the shared secondary account.
- Keep `zeekr_secrets.json` and your captured values **local and private** — they are not committed.

---

## What happens after you send the results back

The values get placed into the repo (no action needed from you beyond sending them):
1. `openzeekr/secrets.properties` (gitignored) gets `EM_*` + shared `PASSWORD_PUBLIC_KEY` /
   `VIN_KEY` / `VIN_IV`, plus `XCHANGER_SIGN_SECRET`, `OVERSEAS_ACCESS_KEY` / `OVERSEAS_SECRET_KEY`
   and `INBOX_AUTH_SECRET`, baked into `libozsecrets.so` at build time.
2. Any corrected hosts go into `Region.LA` in
   `openzeekr/core/src/main/java/com/openzeekr/app/net/Region.kt`.
3. Build check: `cd openzeekr && ./gradlew assembleDebug`.
4. Once login + vehicle status + a command succeed on your real MX car, `Region.LA` is flipped to
   `verified = true` and the README region note/changelog are updated.
