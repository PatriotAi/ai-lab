# OAuth Flows & Token Lifecycle

## OAuth 2.0 PKCE (для SPA/mobile — без client secret)

```javascript
// 1. Згенеруй code_verifier + code_challenge
function genPKCE() {
  const verifier = base64url(crypto.getRandomValues(new Uint8Array(32)));
  return crypto.subtle.digest('SHA-256', new TextEncoder().encode(verifier))
    .then(hash => ({ verifier, challenge: base64url(new Uint8Array(hash)) }));
}

// 2. Authorize URL
const { verifier, challenge } = await genPKCE();
sessionStorage.setItem('pkce_verifier', verifier);
const authUrl = `${AUTH_ENDPOINT}?response_type=code&client_id=${CLIENT_ID}` +
  `&redirect_uri=${REDIRECT}&code_challenge=${challenge}&code_challenge_method=S256` +
  `&scope=${SCOPES}&state=${randomState}`;

// 3. Exchange code → token (з verifier, БЕЗ secret)
const token = await fetch(TOKEN_ENDPOINT, {
  method: 'POST',
  headers: {'Content-Type': 'application/x-www-form-urlencoded'},
  body: new URLSearchParams({
    grant_type: 'authorization_code', code, redirect_uri: REDIRECT,
    client_id: CLIENT_ID, code_verifier: sessionStorage.getItem('pkce_verifier')
  })
}).then(r => r.json());
```

PKCE безпечний для публічних клієнтів — не потребує зберігання client secret.

---

## Refresh Token Rotation

```javascript
// Сучасна практика: кожен refresh видає НОВИЙ refresh token
async function refreshTokens(refreshToken) {
  const res = await fetch(TOKEN_ENDPOINT, {
    method: 'POST',
    headers: {'Content-Type': 'application/x-www-form-urlencoded'},
    body: new URLSearchParams({
      grant_type: 'refresh_token', refresh_token: refreshToken, client_id: CLIENT_ID
    })
  }).then(r => r.json());

  // ВАЖЛИВО: зберігай новий refresh token, старий вже невалідний
  await secureStore('access_token', res.access_token);
  await secureStore('refresh_token', res.refresh_token);  // ← ротація
  return res;
}
```

Якщо старий refresh token використано повторно після ротації → потенційна крадіжка, відкликай всю сесію.

---

## Device Flow (для пристроїв без браузера)

```
1. Пристрій → POST /device/code → отримує user_code + verification_uri
2. Показує користувачу: "Зайди на example.com/device, введи код ABCD-1234"
3. Пристрій опитує POST /token кожні N секунд (interval з відповіді)
4. Поки користувач не підтвердив → {error: "authorization_pending"}
5. Після підтвердження → {access_token, refresh_token}
```

```javascript
async function pollDeviceToken(deviceCode, interval) {
  while (true) {
    await new Promise(r => setTimeout(r, interval * 1000));
    const res = await fetch(TOKEN_ENDPOINT, {
      method: 'POST',
      body: new URLSearchParams({
        grant_type: 'urn:ietf:params:oauth:grant-type:device_code',
        device_code: deviceCode, client_id: CLIENT_ID
      })
    }).then(r => r.json());
    if (res.access_token) return res;
    if (res.error === 'slow_down') interval += 5;
    else if (res.error !== 'authorization_pending') throw new Error(res.error);
  }
}
```

---

## Token Introspection

```javascript
// Перевір чи токен ще валідний (на сервері ресурсів)
async function introspect(token) {
  const res = await fetch(INTROSPECT_ENDPOINT, {
    method: 'POST',
    headers: {'Authorization': `Basic ${btoa(CLIENT_ID+':'+CLIENT_SECRET)}`},
    body: new URLSearchParams({ token })
  }).then(r => r.json());
  return res.active;  // true/false
}
```

---

## Secure Storage (AES-GCM)

```javascript
async function encryptToken(token, password) {
  const enc = new TextEncoder();
  const salt = crypto.getRandomValues(new Uint8Array(16));
  const iv = crypto.getRandomValues(new Uint8Array(12));
  const keyMaterial = await crypto.subtle.importKey(
    'raw', enc.encode(password), 'PBKDF2', false, ['deriveKey']);
  const key = await crypto.subtle.deriveKey(
    {name:'PBKDF2', salt, iterations:100000, hash:'SHA-256'},
    keyMaterial, {name:'AES-GCM', length:256}, false, ['encrypt']);
  const ct = await crypto.subtle.encrypt({name:'AES-GCM', iv}, key, enc.encode(token));
  return { ct: base64(ct), salt: base64(salt), iv: base64(iv) };
}
```

Ніколи не зберігай токени у plaintext localStorage. AES-GCM + PBKDF2 = безпечно.

---

## Session Expiry Monitoring

```javascript
// Проактивний моніторинг — попередь до того як сесія впаде
function monitorSession(token, onExpiring) {
  const { exp } = decodeJwt(token);
  const msUntilExpiry = (exp * 1000) - Date.now();
  const warnAt = msUntilExpiry - 5 * 60_000;  // за 5 хв до expiry
  if (warnAt > 0) setTimeout(() => onExpiring(), warnAt);
}
```
