# Play Store Path (TWA / Bubblewrap)

## TWA — Trusted Web Activity

TWA загортає PWA у нативний Android-контейнер (повноекранний, без браузерного UI):

```
Вимоги:
- PWA на HTTPS (валідний SSL)
- Валідний manifest.json з maskable іконками
- Service worker (offline)
- Lighthouse PWA score ≥ 90
- Digital Asset Links (підтвердження власності домену)
```

---

## Bubblewrap (Google CLI для TWA→APK)

```bash
# Встановлення
npm i -g @bubblewrap/cli

# Ініціалізація з manifest URL
bubblewrap init --manifest https://myapp.com/manifest.json

# Збірка APK/AAB
bubblewrap build
# → app-release-signed.apk + app-release-bundle.aab (для Play Store)
```

---

## Digital Asset Links (обов'язково для TWA)

```json
// Розмісти на https://myapp.com/.well-known/assetlinks.json
[{
  "relation": ["delegate_permission/common.handle_all_urls"],
  "target": {
    "namespace": "android_app",
    "package_name": "com.myapp.twa",
    "sha256_cert_fingerprints": ["AA:BB:CC:..."]  // з твого keystore
  }
}]
```

Без цього TWA показуватиме браузерний URL-бар. З ним — повноекранно як нативний застосунок.

---

## App Signing

```bash
# Згенеруй keystore (зберігай НАДІЙНО — втратиш = не зможеш оновлювати!)
keytool -genkey -v -keystore my-app.keystore \
  -alias my-app -keyalg RSA -keysize 2048 -validity 10000

# Отримай SHA-256 fingerprint для assetlinks.json
keytool -list -v -keystore my-app.keystore -alias my-app | grep SHA256
```

⚠️ **Play App Signing:** Google може керувати ключем підпису. Завантаж upload key, Google підписує фінально. Безпечніше — не втратиш ключ.

---

## Play Store Submission Checklist

```
□ AAB (Android App Bundle), не APK — Play вимагає AAB
□ Іконка 512×512 PNG (high-res)
□ Feature graphic 1024×500
□ Мінімум 2 скриншоти (phone)
□ Privacy policy URL (обов'язково)
□ Content rating (анкета)
□ Target API level ≥ поточний мінімум Google (оновлюється щороку)
□ Data safety form заповнено
```

---

## Capacitor (альтернатива — більше нативних API)

```bash
# Якщо потрібен доступ до нативних API (камера, файли, push)
npm i @capacitor/core @capacitor/cli
npx cap init
npx cap add android
npx cap copy
npx cap open android   # відкриває Android Studio
```

TWA — для простих PWA. Capacitor — коли потрібні нативні плагіни (BLE, NFC, нативний share).

---

## iOS PWA (обмеження)

```
iOS Safari підтримує PWA частково:
✓ Add to Home Screen
✓ Service Worker (offline)
✓ manifest.json (базово)
✗ Web Push (лише з iOS 16.4+, і лише з home screen)
✗ Background Sync (немає)
✗ Деякі Web APIs

Для повноцінного iOS — PWABuilder генерує iOS-пакет, або Capacitor.
```
