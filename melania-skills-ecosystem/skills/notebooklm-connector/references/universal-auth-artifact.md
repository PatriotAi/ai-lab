# Universal Auth Artifact — Google OAuth для NotebookLM

## Коли застосовувати

Автоматично при AUTH_REQUIRED / 403 від будь-якого Google-ресурсу.
Працює на всіх пристроях без встановлення чогось.
Persistent storage зберігає стан між сесіями.

## Дизайн-директива (frontend-design skill)

**Концепція:** "Mission Control" — темна операційна панель.
- Фон: `#0a0f1e` deep navy + SVG grain texture
- Картка: glassmorphism `rgba(255,255,255,0.04)` + `backdrop-filter: blur(20px)`
- Шрифт: Sora (UI) + DM Mono (коди/ID)
- Акценти: Google Blue `#4285F4`, Emerald `#10b981`, Amber `#f59e0b`, Rose `#f43f5e`
- Анімації: `cubic-bezier(0.34,1.56,0.64,1)` slide-up, pulse dots, pop-in success
- НІКОЛИ: Inter, purple gradients, centered hero, generic cards

## Генерувати як React .jsx

Підставити `NOTEBOOK_URL`, `NOTEBOOK_ID`, `TASK` перед генерацією.

```jsx
import { useState, useEffect, useRef } from "react";

const NOTEBOOK_URL = "{URL}";
const NOTEBOOK_ID  = "{ID}";
const TASK         = "{TASK}";  // "об'єднай всі джерела в документ"

const CSS = `
  @import url('https://fonts.googleapis.com/css2?family=Sora:wght@300;400;500;600&family=DM+Mono:ital,wght@0,400;0,500&display=swap');
  *{box-sizing:border-box;margin:0;padding:0}
  body{background:#0a0f1e;font-family:'Sora',sans-serif;color:#e2e8f0;min-height:100vh}
  .grain{position:fixed;inset:0;pointer-events:none;z-index:0;
    background-image:url("data:image/svg+xml,%3Csvg viewBox='0 0 256 256' xmlns='http://www.w3.org/2000/svg'%3E%3Cfilter id='n'%3E%3CfeTurbulence type='fractalNoise' baseFrequency='.9' numOctaves='4' stitchTiles='stitch'/%3E%3C/filter%3E%3Crect width='100%25' height='100%25' filter='url(%23n)' opacity='.04'/%3E%3C/svg%3E");
    opacity:.4}
  .wrap{position:relative;z-index:1;min-height:100vh;display:flex;align-items:center;justify-content:center;padding:24px}
  .card{width:100%;max-width:440px;background:rgba(255,255,255,.04);backdrop-filter:blur(20px);
    border:1px solid rgba(255,255,255,.08);border-radius:20px;padding:36px 32px;
    box-shadow:0 24px 48px rgba(0,0,0,.5),0 0 0 1px rgba(255,255,255,.03);
    animation:up .4s cubic-bezier(.34,1.56,.64,1)}
  @keyframes up{from{opacity:0;transform:translateY(24px) scale(.97)}to{opacity:1;transform:none}}
  .badge{display:inline-flex;align-items:center;gap:6px;font-family:'DM Mono',monospace;
    font-size:10px;font-weight:500;letter-spacing:.12em;text-transform:uppercase;color:#64748b;
    background:rgba(255,255,255,.05);border:1px solid rgba(255,255,255,.07);
    border-radius:6px;padding:4px 10px;margin-bottom:20px}
  .dot{width:6px;height:6px;border-radius:50%;animation:pulse 2s infinite}
  .blue{background:#4285F4;box-shadow:0 0 6px #4285F4}
  .amber{background:#f59e0b;box-shadow:0 0 6px #f59e0b}
  .green{background:#10b981;box-shadow:0 0 6px #10b981}
  .rose{background:#f43f5e;box-shadow:0 0 6px #f43f5e}
  @keyframes pulse{0%,100%{opacity:1}50%{opacity:.4}}
  h2{font-size:22px;font-weight:600;line-height:1.3;color:#f1f5f9;margin-bottom:8px}
  .sub{font-size:13px;color:#64748b;line-height:1.6;margin-bottom:24px}
  .infobox{display:flex;align-items:center;gap:10px;background:rgba(255,255,255,.03);
    border:1px solid rgba(255,255,255,.06);border-radius:10px;padding:12px 14px;margin-bottom:20px}
  .mono{font-family:'DM Mono',monospace;font-size:11px;color:#475569}
  .mono strong{color:#94a3b8;display:block;font-size:10px;margin-bottom:2px}
  .gbtn{display:flex;align-items:center;justify-content:center;gap:12px;width:100%;
    background:linear-gradient(135deg,#4285F4,#357ae8);border:none;border-radius:12px;
    padding:14px 20px;font-size:14px;font-weight:500;color:#fff;cursor:pointer;
    position:relative;overflow:hidden;
    transition:transform .15s,box-shadow .15s;
    box-shadow:0 4px 20px rgba(66,133,244,.35)}
  .gbtn:hover{transform:translateY(-1px);box-shadow:0 8px 28px rgba(66,133,244,.45)}
  .gbtn::after{content:'';position:absolute;inset:0;
    background:linear-gradient(135deg,rgba(255,255,255,.12),transparent);pointer-events:none}
  .sbtn{display:flex;align-items:center;justify-content:center;gap:10px;width:100%;margin-top:12px;
    background:linear-gradient(135deg,#10b981,#059669);border:none;border-radius:12px;
    padding:14px 20px;font-size:14px;font-weight:500;color:#fff;cursor:pointer;
    transition:transform .15s,box-shadow .15s;box-shadow:0 4px 20px rgba(16,185,129,.3)}
  .sbtn:hover{transform:translateY(-1px);box-shadow:0 8px 24px rgba(16,185,129,.4)}
  .spin{width:40px;height:40px;margin:0 auto 20px;
    border:2px solid rgba(255,255,255,.08);border-top:2px solid #4285F4;
    border-radius:50%;animation:spin .8s linear infinite}
  @keyframes spin{to{transform:rotate(360deg)}}
  .ok{width:56px;height:56px;margin:0 auto 20px;background:rgba(16,185,129,.12);
    border:1px solid rgba(16,185,129,.3);border-radius:50%;
    display:flex;align-items:center;justify-content:center;font-size:24px;
    animation:pop .4s cubic-bezier(.34,1.56,.64,1)}
  @keyframes pop{from{transform:scale(0);opacity:0}to{transform:scale(1);opacity:1}}
  .chip{display:flex;align-items:center;gap:10px;background:rgba(16,185,129,.08);
    border:1px solid rgba(16,185,129,.2);border-radius:10px;padding:10px 14px;margin-bottom:20px}
  .av{width:32px;height:32px;border-radius:50%;
    background:linear-gradient(135deg,#4285F4,#10b981);
    display:flex;align-items:center;justify-content:center;font-size:14px;font-weight:600}
  .nm{font-size:13px;font-weight:500;color:#e2e8f0}
  .em{font-size:11px;color:#64748b}
  .saved{font-size:11px;color:#10b981;margin-top:4px}
  textarea{width:100%;min-height:120px;background:rgba(255,255,255,.03);
    border:1px solid rgba(255,255,255,.08);border-radius:10px;padding:12px 14px;
    font-family:'Sora',sans-serif;font-size:13px;color:#e2e8f0;resize:vertical;outline:none;
    transition:border-color .2s;margin-top:8px}
  textarea:focus{border-color:rgba(66,133,244,.4)}
  textarea::placeholder{color:#334155}
  .hint{font-size:11px;color:#334155;margin-top:16px;text-align:center}
  a{color:#4285F4;text-decoration:none}
  ol{padding-left:18px}
  ol li{font-size:13px;color:#64748b;margin-bottom:6px;line-height:1.5}
  .storage-badge{display:inline-flex;align-items:center;gap:4px;
    font-size:10px;color:#10b981;background:rgba(16,185,129,.08);
    border:1px solid rgba(16,185,129,.15);border-radius:4px;padding:2px 6px;margin-top:8px}
`;

const GIcon = () => (
  <svg width="18" height="18" viewBox="0 0 18 18" fill="none">
    <path fill="#fff" d="M9 3.48c1.69 0 2.83.73 3.48 1.34l2.54-2.48C13.46.89 11.43 0 9 0 5.48 0 2.44 2.02.96 4.96l2.91 2.26C4.6 5.05 6.62 3.48 9 3.48z"/>
    <path fill="#fff" d="M17.64 9.2c0-.74-.06-1.28-.19-1.84H9v3.34h4.96c-.1.83-.64 2.08-1.84 2.92l2.84 2.2c1.7-1.57 2.68-3.88 2.68-6.62z"/>
    <path fill="#fff" d="M3.88 10.78A5.54 5.54 0 0 1 3.58 9c0-.62.11-1.22.29-1.78L.96 4.96A9 9 0 0 0 0 9c0 1.45.35 2.82.96 4.04l2.92-2.26z"/>
    <path fill="#fff" d="M9 18c2.43 0 4.47-.8 5.96-2.18l-2.84-2.2c-.76.53-1.78.9-3.12.9-2.38 0-4.4-1.57-5.12-3.74L.97 13.04C2.45 15.98 5.48 18 9 18z"/>
  </svg>
);

export default function NotebookLMAuth() {
  const [phase, setPhase] = useState("boot");
  const [user, setUser]   = useState(null);
  const [content, setContent] = useState("");
  const [manual, setManual]   = useState("");
  const [err, setErr]         = useState("");
  const [storageSaved, setStorageSaved] = useState(false);
  const styleRef = useRef(null);

  // ── Inject styles ─────────────────────────────────────────────────────────
  useEffect(() => {
    const s = document.createElement("style");
    s.textContent = CSS;
    document.head.appendChild(s);
    styleRef.current = s;
    return () => s.remove();
  }, []);

  // ── Restore saved state from persistent storage ───────────────────────────
  useEffect(() => {
    (async () => {
      try {
        const saved = await window.storage.get(`nlm-auth:${NOTEBOOK_ID}`);
        if (saved) {
          const data = JSON.parse(saved.value);
          if (data.user && data.content) {
            setUser(data.user);
            setContent(data.content);
            setPhase("done");
            setStorageSaved(true);
            return;
          }
        }
      } catch { /* no saved state */ }

      // Load Google Identity Services
      const script = document.createElement("script");
      script.src = "https://accounts.google.com/gsi/client";
      script.async = true;
      script.onload = () => setPhase("ready");
      script.onerror = () => { setErr("Could not load Google Auth"); setPhase("error"); };
      document.head.appendChild(script);
    })();
  }, []);

  // ── Google auth callback ──────────────────────────────────────────────────
  const handleCredential = async (resp) => {
    setPhase("authing");
    const payload = JSON.parse(atob(resp.credential.split(".")[1]));
    const u = { name: payload.name, email: payload.email };
    setUser(u);
    setPhase("extracting");

    try {
      const r = await fetch(
        "https://www.googleapis.com/drive/v3/files?pageSize=20&fields=files(id,name,mimeType)",
        { headers: { Authorization: `Bearer ${resp.credential}` } }
      );
      const c = r.ok ? JSON.stringify(await r.json(), null, 2) : "";
      setContent(c);

      // Persist to storage
      if (c) {
        try {
          await window.storage.set(`nlm-auth:${NOTEBOOK_ID}`, JSON.stringify({ user: u, content: c }));
          setStorageSaved(true);
        } catch { /* storage not available */ }
      }

      setPhase(c ? "done" : "manual");
    } catch {
      setPhase("manual");
    }
  };

  const signIn = () => {
    if (!window.google) return;
    window.google.accounts.id.initialize({
      client_id: "YOUR_CLIENT_ID.apps.googleusercontent.com",
      callback: handleCredential,
    });
    window.google.accounts.id.prompt();
  };

  const send = () => {
    const text = content || manual;
    if (!text.trim()) return;
    sendPrompt(`Авторизація успішна. Контент з NotebookLM (${NOTEBOOK_URL}):\n\n${text}\n\nЗавдання: ${TASK}`);
  };

  const clearSaved = async () => {
    try { await window.storage.delete(`nlm-auth:${NOTEBOOK_ID}`); } catch {}
    setPhase("boot");
    setUser(null); setContent(""); setStorageSaved(false);
    window.location.reload();
  };

  const dotClass = { boot:"blue", ready:"blue", authing:"amber",
                     extracting:"amber", done:"green", manual:"amber", error:"rose" };
  const label    = { boot:"ініціалізація", ready:"готово", authing:"авторизація",
                     extracting:"витяг", done:"успішно", manual:"ручний режим", error:"помилка" };

  return (
    <div className="wrap">
      <div className="grain" />
      <div className="card">
        <div className="badge">
          <span className={`dot ${dotClass[phase]}`} />
          NotebookLM · {label[phase]}
        </div>

        {phase === "boot" && <><div className="spin"/><h2>Ініціалізація...</h2></>}

        {phase === "ready" && <>
          <h2>Авторизація для доступу</h2>
          <p className="sub">NotebookLM потребує активної Google-сесії.</p>
          <div className="infobox">
            <span>📒</span>
            <div className="mono"><strong>Notebook ID</strong>{NOTEBOOK_ID}</div>
          </div>
          <button className="gbtn" onClick={signIn}><GIcon/>Увійти через Google</button>
          <p className="hint">Claude не отримує твій пароль</p>
        </>}

        {(phase === "authing" || phase === "extracting") && <>
          <div className="spin"/>
          {user && <div className="chip">
            <div className="av">{user.name?.[0]}</div>
            <div><div className="nm">{user.name}</div><div className="em">{user.email}</div></div>
          </div>}
          <h2>{phase === "authing" ? "Авторизація..." : "Витяг даних..."}</h2>
        </>}

        {phase === "done" && <>
          <div className="ok">✓</div>
          <div className="chip">
            <div className="av">{user?.name?.[0]}</div>
            <div>
              <div className="nm">{user?.name}</div>
              <div className="em">{user?.email}</div>
              {storageSaved && <div className="saved">💾 Збережено локально</div>}
            </div>
          </div>
          <h2>Контент отримано</h2>
          <p className="sub">Натисни — Claude виконає завдання автоматично.</p>
          <button className="sbtn" onClick={send}>↑ Надіслати Claude · {TASK}</button>
          {storageSaved && <p className="hint" style={{marginTop:12}}>
            Сесія збережена. <a href="#" onClick={e=>{e.preventDefault();clearSaved()}}>Очистити</a>
          </p>}
        </>}

        {phase === "manual" && <>
          <div className="chip">
            <div className="av">{user?.name?.[0]}</div>
            <div><div className="nm">{user?.name}</div><div className="em">{user?.email}</div></div>
          </div>
          <h2>Скопіюй контент вручну</h2>
          <ol>
            <li>Відкрий <a href={NOTEBOOK_URL} target="_blank" rel="noreferrer">свій Notebook ↗</a></li>
            <li>Studio → Briefing Doc → скопіюй, або відкрий кожне джерело → Ctrl+A → Copy</li>
            <li>Вставте нижче та надішли</li>
          </ol>
          <textarea placeholder="Вставте контент..." value={manual} onChange={e=>setManual(e.target.value)}/>
          <button className="sbtn" onClick={send}>↑ Надіслати Claude · {TASK}</button>
        </>}

        {phase === "error" && <>
          <h2>⚠ Помилка</h2><p className="sub">{err}</p>
        </>}
      </div>
    </div>
  );
}
```

## Persistent storage API

`window.storage.set(key, value)` — зберегти між сесіями
`window.storage.get(key)` → `{ value }` — відновити
`window.storage.delete(key)` — очистити

Key pattern: `nlm-auth:{NOTEBOOK_ID}` — унікальний для кожного Notebook.
Зберігає: `{ user: {name, email}, content: "extracted data" }`.

## Адаптація TASK константи

- `"об'єднай всі джерела в суцільний документ"`
- `"проведи глибокий аналіз всіх джерел"`
- `"витягни ключові факти та статистику"`
- `"підготуй Briefing Doc на основі контенту"`
