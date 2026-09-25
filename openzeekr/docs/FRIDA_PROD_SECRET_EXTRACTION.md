# Runtime `prod_secret` Extraction (Frida) — LA / Mexico

## Why this doc exists

Login on the Mexico (`com.zeekr.global`, region **EM**) account fails at the TSP
gateway with:

```
079025 request failed signature authentication
```

The login flow is:

1. usercenter login — signed with **HMAC keys** (`hmac_access_key` / `hmac_secret_key`)
2. `tspCode`
3. **bearer_login on the TSP gateway — signed with `X-SIGNATURE` = HMAC-SHA256, key = `prod_secret`**

`079025` is thrown **only at step 3**, which means:

- ✅ `EM_HMAC_ACCESS_KEY` / `EM_HMAC_SECRET_KEY` are **correct** (usercenter login passed).
- ❌ The `prod_secret` the gateway expects is **not** any of the static strings pulled
  from the 1.5.5 APK (all candidates returned 079025).

The static path is exhausted for `prod_secret`. We need the **runtime** value via Frida.

---

## Which app version to use: **1.5.5 (the APK you already sideloaded)**

- `prod_secret` is tied to the **package + region** (`com.zeekr.global` / EM), **not** the
  app version. 1.5.5 and 1.6.6 hit the same live gateway, so the runtime `prod_secret`
  is the same value in both. **You do not need 1.6.6.**
- Frida reads the key **at the moment the app computes the HMAC**, so obfuscation / iWall /
  ECIES on newer versions is irrelevant — but newer versions add more **root/tamper
  detection**, which makes the app harder to run instrumented. Older = fewer defenses.
- You already have the **1.5.5 APK** on disk (you sideloaded it to downgrade). Reuse it.

Below it's called `zeekr-1.5.5.apk` — substitute your real filename/path.

---

## Terminology — where each command runs

- **Host** = your Windows PC (Android Studio, `adb`, Python, `objection`, `frida`).
  All `pip` / `objection` / `frida` / `adb` commands run here, in a **PowerShell** terminal.
- **Device** = your rooted phone over USB. You only type commands *on the device* in
  Route B, inside an `adb shell` → `su` shell (and even then, the module route avoids it).

Confirm the phone is connected (host):

```
adb devices
```

You should see one device listed as `device` (not `unauthorized`).

---

## The hook — `dump.js`

Don't try to locate the obfuscated signing function. Just dump every HMAC/AES key as it's
constructed. Save this as `dump.js` in your working folder:

```js
Java.perform(function () {
  var SKS = Java.use('javax.crypto.spec.SecretKeySpec');
  SKS.$init.overload('[B', 'java.lang.String').implementation = function (key, alg) {
    var hex = '', utf8 = '';
    for (var i = 0; i < key.length; i++) {
      var b = key[i] & 0xff;
      hex += ('0' + b.toString(16)).slice(-2);
      utf8 += String.fromCharCode(b);
    }
    console.log('[KEY] alg=' + alg + ' len=' + key.length + '\n  hex=' + hex + '\n  utf8=' + utf8);
    return this.$init(key, alg);
  };
  var IV = Java.use('javax.crypto.spec.IvParameterSpec');
  IV.$init.overload('[B').implementation = function (iv) {
    var hex = ''; for (var i = 0; i < iv.length; i++) hex += ('0' + (iv[i] & 0xff).toString(16)).slice(-2);
    console.log('[IV] hex=' + hex);
    return this.$init(iv);
  };
});
```

---

## Route A — objection + frida-gadget (no root, no frida-server, no SELinux crash)

This repackages the 1.5.5 APK with the Frida **gadget** baked inside. The gadget runs
**inside the app's own process**, so the memory/SELinux error that crashed the phone can't
happen. **Yes — you pass the APK to the command.**

### A1. Prerequisites (host, one-time)

Use **Python 3.11 or 3.12** (3.13 often has no matching Frida wheel):

```
py -3.12 -m venv frida-env
.\frida-env\Scripts\Activate.ps1
pip install objection "frida==16.7.19" "frida-tools==13.7.1"
```

`objection patchapk` also needs these on PATH:

- **Java** (for `apktool`) — Android Studio's JBR works, or install a JDK.
- **apktool** — `apktool.jar` + `apktool.bat` wrapper in a PATH folder.
- **`zipalign` + `apksigner`** — from the Android SDK build-tools you already have, e.g.
  `C:\Users\RH753JV\AppData\Local\Android\Sdk\build-tools\<version>\`

Verify (host):

```
java -version
apktool --version
zipalign
apksigner
```

### A2. Handle split APKs

- Single `.apk` → skip this step.
- `.xapk` / `.apks` / `.apkm` bundle (multiple splits) → objection can't patch it directly.
  Either rename to `.zip`, extract, and use the inner `base.apk`, or merge:
  `java -jar APKEditor.jar m -i <bundle> -o zeekr-1.5.5.apk`

### A3. Patch the APK (host)

Run **in the folder containing the APK** (or use a full path):

```
objection patchapk -s zeekr-1.5.5.apk
```

Choose **arm64** if prompted (S8 is arm64-v8a). Output: **`zeekr-1.5.5.objection.apk`**.

### A4. Install the patched APK (host)

The repackage has a different signature, so remove the store version first:

```
adb uninstall com.zeekr.global
adb install zeekr-1.5.5.objection.apk
```

### A5. Attach and hook (host + phone)

1. **Phone:** launch the Zeekr app. The gadget loads and listens.
2. **Host:** attach and load the hook:

```
frida -U Gadget -l dump.js
```

3. **Phone:** log in with your **Mexico account**. Watch the host terminal.

### A6. If the app crashes on launch

1.5.5 has a signature/tamper check that rejects the repackage → use **Route B**.

---

## Route B — frida-server via a KernelSU module (keeps SELinux enforcing)

The original failure (`frida-ps -U → unexpected failure while trying to allocate memory`,
then a kernel panic on `setenforce 0`) happened because `frida-server` was launched from an
`adb su` shell, landing it in a **restricted SELinux domain**. Running it as a **KernelSU
module service** launches it in the correct context — **without** touching `setenforce`.

### B1. Install the frida module (phone)

1. Open **KernelSU Manager** → **Modules**.
2. Install a **MagiskFrida** / **frida-server** module (KernelSU-compatible flashable zip;
   MagiskFrida is the common one). Use a build matching **Frida 16.7.x**.
3. **Reboot** the phone.

This auto-starts `frida-server` in the right domain on every boot — you no longer run
`./frida-server` manually.

### B2. Verify from the host (host)

```
frida-ps -U
```

Should list processes **without** the memory error and **without** disabling SELinux.

### B3. Hook (host + phone)

With the **normal, unmodified** 1.5.5 app installed (no repackage needed in Route B):

```
frida -U -f com.zeekr.global -l dump.js
```

Then log in with your Mexico account on the phone and watch the output.

### B4. Route B nuances / troubleshooting

These are the gotchas that bite most on a Samsung S8 (Exynos) + KernelSU:

- **Version lockstep (most common failure).** Host `frida` and the device module **must be
  the same version**. Mismatch shows as `unable to connect to remote frida-server:
  closed` / `connection refused` / `failed to load script`. Fix: match them —
  `pip install "frida==<module version>"` on the host, or install a module matching your host.
- **KernelSU module vs. manual binary — don't mix.** If you also left a manually-copied
  `frida-server` running, you'll get `address already in use (127.0.0.1:27042)`. Pick one.
  Kill the manual one: on the phone, `su -c "pkill -f frida-server"`, or reboot and rely
  only on the module.
- **Manual `frida-server` fallback done right (if you skip the module).** The memory/SELinux
  error comes from the wrong domain, *not* from needing permissive mode. Launch it so it
  inherits a usable context and detach it from the shell:
  ```
  adb shell
  su
  setsid /data/local/tmp/frida-server -D
  ```
  Keep SELinux **enforcing**. Do **not** run `setenforce 0` — on this phone it panics.
  If you still get the allocation error in enforcing mode, the **module route (B1)** is the
  reliable fix; the manual binary in some KernelSU setups simply can't get a working domain.
- **Bind to a non-default port if 27042 is contested.** Device:
  `setsid /data/local/tmp/frida-server -l 127.0.0.1:27055 -D`; host:
  `frida-ps -H 127.0.0.1:27055` (after `adb forward tcp:27055 tcp:27055`).
- **`frida-ps` returns nothing / hangs.** Usually the module didn't start or version
  mismatch. Check it's running: `su -c "ps -A | grep frida"`. If absent, re-flash/enable the
  module and reboot.
- **App won't start under `-f` (root/tamper detection).** Newer builds detect root; that's
    another reason to stay on **1.5.5**. If 1.5.5 still detects root, attach **after** manual
  launch instead of spawning: open the app by hand, then `frida -U -n "Zeekr" -l dump.js`
  (or use the exact process name from `frida-ps -Uai`).
- **Binary location & perms (manual route only).** Push to `/data/local/tmp`, then
  `su -c "chmod 755 /data/local/tmp/frida-server"`. Use the **arm64** server build
  (`frida-server-16.7.19-android-arm64`), decompressed from the `.xz`.
- **USB / adb hiccups.** If `frida-ps -U` can't find the device but `adb devices` shows it,
  re-run `adb kill-server && adb start-server`, and make sure only one Frida version's
  `frida-tools` is on PATH (the venv).

---

## Which to try first

- **Route A first** — sidesteps root entirely and dodges the SELinux/kernel-panic problem.
  Only risk: the repackage may trip a tamper check on launch.
- **Route B** if the patched app won't start — needs the KernelSU module but no repackaging.

---

## After you capture it

Look at the **`HmacSHA256`** key printed around login — that's `prod_secret`. Then compare
to the static `37b532eaa4aa7f23c2567f2707e5d952`:

- **Different** → that's the answer. Set in `openzeekr/secrets.properties`:
  ```
  EM_PROD_SECRET=<value>
  XCHANGER_SIGN_SECRET=<same value>
  ```
  then rebuild `assembleDebug`.
- **Identical** → the secret was never the problem; the culprit is a baked global-app
  constant differing for Mexico. From the same run, also grab the **`x-app-id`** and
  **`app-authorization`** header values the real app sends, and wire those instead.

Also note any **`AES`** key + **`IV`** printed — confirms `vin_key` / `vin_iv`.
