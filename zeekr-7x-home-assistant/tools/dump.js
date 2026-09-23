// Reads the three runtime secrets from the Zeekr app: prod_secret, vin_key, vin_iv.
//
// Run this only AFTER you have LOGGED IN to the app once — the values don't exist
// in memory until the first signed request initialises the iWall SDK.
//
// Class/method names below are for com.zeekr.overseas v3.0.x. Two methods are
// tried:
//   A) read the already-decrypted values straight from the app's getters
//      (no jadx, no blobs needed) — the easy path.
//   B) fall back to decrypting the blobs yourself (paste them from xn/a.java).
// See QUICKSTART.md if both fail on a newer app version.

Java.perform(function () {
  function looksReal(v) { return v !== null && v !== undefined && ('' + v).length >= 8; }
  var out = { _method: null };

  // ---- Method A: cached getters ----
  try {
    var M = Java.use('com.zeekr.snc.log.m');
    var inst = M.a.value;              // static instance holding the decrypted fields
    if (inst !== null) {
      out.prod_secret = '' + inst.k(); // 32 hex chars
      out.vin_key     = '' + inst.j(); // 16 chars
      out.vin_iv      = '' + inst.c(); // 16 chars
      if (looksReal(out.prod_secret)) { out._method = 'getters'; }
    }
  } catch (e) { out._getterError = '' + e; }

  // ---- Method B: decrypt the blobs (fallback) ----
  if (!looksReal(out.prod_secret)) {
    try {
      // Paste the three base64 blobs from your APK's xn/a.java here:
      var PROD = '<xn.a.c base64 from your apk>';
      var VKEY = '<xn.a.a base64 from your apk>';
      var VIV  = '<xn.a.l base64 from your apk>';
      var YA = Java.use('yn.a').$new();  // static YA.a.value may be null; $new works
      var P  = Java.use('com.geely.snc.security.api.model.EnvType').PRODUCT.value;
      out.prod_secret = '' + YA.c(P, PROD);
      out.vin_key     = '' + YA.c(P, VKEY);
      out.vin_iv      = '' + YA.c(P, VIV);
      if (looksReal(out.prod_secret)) { out._method = 'blobs'; }
    } catch (e) { out._blobError = '' + e; }
  }

  send(out);
});
