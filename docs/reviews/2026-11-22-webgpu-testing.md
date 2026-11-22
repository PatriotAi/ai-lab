# Як перевірити локальну ШІ-модель (WebLLM на WebGPU) до злиття — дослідження (2026-11-22)

**Запит:** сесія think-like-gpt (PR #15, `@mlc-ai/web-llm` 0.2.87 → 0.2.89) просила перевірити
справжнє завантаження моделі й відповідь на WebGPU в емуляторі; власник доручив визначити й
застосувати все потрібне, щоб це стало можливим. Теги: [E] перевірено ділом · [C] джерело · [S] гіпотеза.

## Що виміряно

| Середовище | WebGPU | Модель завантажилась | Відповідь | Доказ |
|---|---|---|---|---|
| Віртуальний Android (емулятор, API 34, Chrome 113, програмна графіка) | ❌ «webgpu appears to be disabled», `requestAdapter` — failed | — | — | [E] запуск 45031743098, знімок `webgpureport.org` у `android-sim-results` |
| Настільний Chromium 153 без екрана + SwiftShader (`--enable-unsafe-webgpu --use-webgpu-adapter=swiftshader --enable-features=Vulkan --enable-unsafe-swiftshader`), лише на `localhost` (безпечний контекст) | ✅ адаптер `google/swiftshader`, буфери до 1 ГБ, **без** `shader-f16` | ✅ WebLLM 0.2.89: Qwen3-0.6B-q4f32 (6,7 с), SmolLM2-360M-q4f32 (5,7 с) — «Finish loading on WebGPU» | ❌ процес графіки Chrome падає (`exit_code=5`) під час обчислення, «Device was lost»; не допомогли `--disable-gpu-watchdog`, `--disable-dev-shm-usage`, повний Chromium замість headless-shell | [E] прогін у сесії 2026-11-22 (журнали — у звіті власнику) |

Чому Android-емулятор не годиться [C]: Chrome вмикає WebGPU на Android з версії 121, лише на
Android 12+ і графіці Qualcomm/ARM ([Chrome 121](https://developer.chrome.com/blog/new-in-webgpu-121)).
В образі емулятора Chrome 113 і програмна графіка — обидві умови не виконано; новіший Chrome
офіційно ставиться лише через Play Store з обліковим записом Google.

## Що з цього випливає

1. **Генерацію відповіді без справжньої відеокарти перевірити не вдалося** — ні в емуляторі, ні
   в програмному WebGPU. Найдешевша справжня перевірка — **справжній телефон** (Chrome 121+,
   Android 12+, Qualcomm/ARM).
2. **Програмний WebGPU корисний для решти**: виявлення WebGPU, список моделей, **завантаження**
   моделі, аналіз пристрою, повідомлення про нестачу пам'яті (його можна імітувати, підставивши
   до старту сторінки `navigator.deviceMemory` і менші ліміти адаптера). Це автоматизується
   безкоштовно на раннері GitHub — кандидат в адаптер «web-gpu» для `sim-harness` (етап 3 розбору
   `2026-11-21-simulation-toolchain.md`).
3. **Справжні телефони в хмарі безкоштовно** [C]: Firebase Test Lab, тариф Spark — 5 запусків на
   день на фізичних пристроях ([квоти](https://firebase.google.com/docs/test-lab/usage-quotas-pricing)).
   Потрібні: проєкт Firebase і ключ сервісного облікового запису як секрет GitHub (дія
   власника), невеликий тестовий APK, що відкриває сторінку в Chrome і знімає екран, і ключ
   Vercel для закритої тестової копії. Не перевірено, чи на пристроях Test Lab Chrome справді
   дає WebGPU [S].
4. **Відеокарта на раннері GitHub** — лише платні «великі» раннери; не підходить під «завжди
   безкоштовно».

## Межі цього дослідження
- Програмний WebGPU прогнано в хмарній сесії (4 ядра, 15 ГБ), не на раннері GitHub [E лише для сесії].
- Чи падіння процесу графіки — обмеження SwiftShader чи конкретних ядер WebLLM, не з'ясовано [S].

## Рецепт автотесту без відеокарти (перевірено в цій сесії)

Що перевіряє: WebGPU є · модель завантажується на WebGPU · (окремо) повідомлення про нестачу
пам'яті. **Не** перевіряє генерацію відповіді — для неї потрібна справжня відеокарта.

```js
// Playwright, Chromium 139+. Сторінку відкривати з http://localhost:… (безпечний контекст).
const browser = await chromium.launch({ args: [
  '--enable-unsafe-webgpu', '--use-webgpu-adapter=swiftshader', '--enable-features=Vulkan',
  '--enable-unsafe-swiftshader', '--enable-dawn-features=allow_unsafe_apis' ] });
const ctx = await browser.newContext();
// Імітація «телефона з ~3 ГБ» — ДО завантаження сторінки:
await ctx.addInitScript(() => {
  Object.defineProperty(navigator, 'deviceMemory', { get: () => 3 });
  const orig = GPUAdapter.prototype.requestDevice;   // за потреби — менші ліміти адаптера
  GPUAdapter.prototype.requestDevice = function (d) { return orig.call(this, d); };
});
// Модель — лише варіант q4f32 (SwiftShader не має shader-f16), напр. Qwen3-0.6B-q4f32_1-MLC.
// Ознака успіху завантаження: текст прогресу «Finish loading on WebGPU».
```
