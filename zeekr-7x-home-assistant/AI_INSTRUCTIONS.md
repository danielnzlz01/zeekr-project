# AI runbook: connect a Zeekr (EU) to Home Assistant

Give this file to a capable AI coding assistant that has: shell access, `adb` to
a rooted Android device, `jadx`, `frida`/`frida-tools`, and access to your Home
Assistant config (SSH or the config dir). It tells the assistant exactly what to
do and — importantly — what has already been figured out, so it doesn't repeat
the dead ends.

## Scope and safety (read this to the user first)

You are helping the user read **their own** Zeekr vehicle's data into **their
own** Home Assistant, the same access the official app has. This is owner-access,
consistent with the existing community tools. Do **not**: access a vehicle the
user doesn't own; publish decrypted secret values (they are app-global — the user
extracts their own); or proceed if the user cannot confirm ownership.

Stop and ask the user whenever a step needs their credentials, their device
unlocked, or a physical action. Never type or echo their password in a command;
have them place it in a file you read, or drive the app login yourself only with
their explicit go-ahead.

## What is already known (do not re-derive)

- Integration: `Fryyyyy/zeekr_homeassistant` (`custom_components/zeekr_ev`), which
  pulls the `zeekr_ev_api` client.
- **The stock PyPI `zeekr_ev_api` signs requests correctly** — its signing code is
  byte-identical to GitHub `main`, so there is no signature bug and `use_local_api`
  is **optional** (not a fix). `main` only carries a later relogin/auth-header fix
  in `client.py`; using it is a minor optional upgrade, unrelated to `079025`.
- **`X-APP-ID` = `ZEEKRCNCH001M0001` is correct for EU.** The app picks it by
  brand (`wo/j.e`), not region. Do not treat it as the bug.
- **`prod_secret`, `vin_key`, `vin_iv` are iWall ECIES blobs decrypted at
  runtime** (`libiwallca.so`); the static `wysie/zeekr_key_extractor` candidates
  and the "old-APK VIN key" trick do **not** work for v3.0.x EU. Extract them
  with Frida. Static extractor IS correct for `hmac_access_key`,
  `hmac_secret_key`, `password_public_key` (run with `--region EU`).
- Code paths: signing key `com.zeekr.snc.log.m.k()` = `ko.l.e(PRODUCT)` =
  decrypt `xn.a.c`. `vin_key` = `m.j()` = decrypt `xn.a.a`. `vin_iv` = `m.c()` =
  decrypt `xn.a.l`. Decryptor is `yn.a.c(EnvType.PRODUCT, <blob>)`; `EnvType` is
  `com.geely.snc.security.api.model.EnvType`.
- **Frida must be 16.x**, not 17 (17 dropped the built-in Java bridge →
  `Java is not defined`).
- The decryptor **caches** and checks the cache first, so after the app logs in
  once, calling `yn.a.$new().c(PRODUCT, blob)` returns the cached plaintext even
  though `SecuritySuite.D()` gating would otherwise block a cold call.
- `frida-ps` shows the process as `ZEEKR`; **attach by PID**, not name.

## Procedure

1. **Confirm ownership and the plan** with the user. Get: their country code, and
   which app version their account uses (match it on the extraction device).
2. **Second account.** Have the user create a second Zeekr account and share the
   car to it. HA will use this account so the user's own phone app stays logged
   in.
3. **Static keys.** Get the app's split APKs — it need not come from any specific
   device; a given version is the same APK everywhere. Download a current v3.0.x
   from APKPure (https://apkpure.com/zeekr/com.zeekr.overseas); it's an `.xapk`
   (zip of `base` + `split_config.arm64_v8a` + `split_config.xxhdpi`). Run
   `wysie/zeekr_key_extractor --region <REGION>` against those to get
   `hmac_access_key`, `hmac_secret_key`, `password_public_key`.
4. **Read the blobs.** `jadx` the base APK; from `xn/a.java` copy the base64
   values of `xn.a.c` (prod_secret), `xn.a.a` (vin_key), `xn.a.l` (vin_iv).
5. **Runtime extract.** On a rooted device: install the matching app version,
   start `frida-server` 16.x as root, have the user log in with the second
   account (this initializes the iWall SDK), then attach by PID and call
   `yn.a.$new().c(EnvType.PRODUCT.value, blob)` for each of the three blobs.
   Expect: prod_secret = 32 hex, vin_key/vin_iv = 16 chars each.
6. **Install the integration** (`Fryyyyy/zeekr_homeassistant`) via HACS. The stock
   PyPI `zeekr_ev_api` signs correctly, so no source copy is needed.
7. **Configure.** Drive the `zeekr_ev` config flow (UI, or the config-entries
   flow API) with: second-account username/password, country code, drive side
   `lhd`, the three static keys, and the three runtime keys. `use_local_api` is
   optional (leave it off). If HA has no `python3`, edit
   `.storage/core.config_entries` with `jq` and restart HA to apply corrections.
8. **Verify.** `sensor.zeekr_api_status` = `Connected`; press the poll button;
   expect vehicle entities (battery, range, locks, …) to appear. If vehicle
   status fails with `Decrypt X-VIN failed`, the vin_key/vin_iv are still the
   static ones — replace with the runtime values.
9. **Clean up.** Uninstall the app from the extraction device (else the second
   account is logged in twice and the sessions fight). Stop/remove frida-server.
   Have the user revoke any temporary HA token and delete any password file.

## Debugging map (server responses)

- `Invalid access key` (0001): wrong HMAC keys or wrong region.
- `9300` at `_do_login_request`: country/region vs key mismatch.
- `Signature authentication failed` (079025) at `_bearer_login`: wrong
  `prod_secret` — it's runtime-only on 3.0.x, the static candidates fail;
  runtime-extract it.
- `Decrypt X-VIN failed` (079025) at vehicle status: wrong vin_key/vin_iv
  (runtime-extract them).

## Notes on the dashboard (optional last step)

Once entities exist, `ngocjohn/vehicle-status-card` (HACS) gives a rich vehicle
card. Install the resource via HACS, then add it to a dashboard, mapping the
`sensor.zeekr_*` / `lock.zeekr_*` / `device_tracker.zeekr_*` entities.
