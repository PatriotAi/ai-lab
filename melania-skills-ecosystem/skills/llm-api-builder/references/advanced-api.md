# Advanced Claude API

## Prompt Caching (економія до 90% на повторюваному контексті)

```python
# Кешуй великий стабільний контекст (system prompt, документи)
response = client.messages.create(
    model="claude-opus-4-5",
    max_tokens=1024,
    system=[
        {"type": "text", "text": "You are an expert assistant."},
        {
            "type": "text",
            "text": large_document,           # великий стабільний контекст
            "cache_control": {"type": "ephemeral"}  # ← кешується на 5 хв
        }
    ],
    messages=[{"role": "user", "content": question}]
)
# Наступні запити з тим самим кешованим блоком — 90% дешевше на cached tokens
```

**Коли вмикати:** великий system prompt, документи що повторюються між запитами, few-shot приклади. Мінімум 1024 токени для кешування.

---

## Citations API (відповіді з посиланнями на джерела)

```python
response = client.messages.create(
    model="claude-opus-4-5",
    max_tokens=1024,
    messages=[{
        "role": "user",
        "content": [
            {
                "type": "document",
                "source": {"type": "text", "media_type": "text/plain", "data": doc_text},
                "title": "Research Paper",
                "citations": {"enabled": True}    # ← вмикає цитування
            },
            {"type": "text", "text": "Summarize the key findings."}
        ]
    }]
)
# Відповідь міститиме citation блоки з точними посиланнями на джерело
```

---

## Vision (аналіз зображень)

```python
import base64
with open("chart.png", "rb") as f:
    img_data = base64.standard_b64encode(f.read()).decode()

response = client.messages.create(
    model="claude-opus-4-5",
    max_tokens=1024,
    messages=[{
        "role": "user",
        "content": [
            {"type": "image", "source": {
                "type": "base64", "media_type": "image/png", "data": img_data
            }},
            {"type": "text", "text": "What trends does this chart show?"}
        ]
    }]
)
```

---

## PDF Support (документи нативно)

```python
with open("report.pdf", "rb") as f:
    pdf_data = base64.standard_b64encode(f.read()).decode()

response = client.messages.create(
    model="claude-opus-4-5",
    max_tokens=2048,
    messages=[{
        "role": "user",
        "content": [
            {"type": "document", "source": {
                "type": "base64", "media_type": "application/pdf", "data": pdf_data
            }},
            {"type": "text", "text": "Extract all tables from this PDF."}
        ]
    }]
)
# Claude бачить і текст, і візуальну структуру PDF (таблиці, графіки)
```

---

## Files API (для великих/повторюваних файлів)

```python
# Завантаж файл один раз, посилайся багато разів
uploaded = client.files.upload(file=open("large_dataset.pdf", "rb"))

response = client.messages.create(
    model="claude-opus-4-5",
    max_tokens=1024,
    messages=[{
        "role": "user",
        "content": [
            {"type": "document", "source": {"type": "file", "file_id": uploaded.id}},
            {"type": "text", "text": "Analyze this."}
        ]
    }]
)
# Файл не пересилається з кожним запитом — лише посилання
```

---

## Structured Output через Tool Use

```python
# Гарантований JSON через "інструмент" зі схемою
extract_tool = {
    "name": "extract_data",
    "description": "Extract structured data",
    "input_schema": {
        "type": "object",
        "properties": {
            "name": {"type": "string"},
            "sentiment": {"type": "string", "enum": ["positive","neutral","negative"]},
            "score": {"type": "number"}
        },
        "required": ["name", "sentiment", "score"]
    }
}
response = client.messages.create(
    model=MODEL, max_tokens=1024,
    tools=[extract_tool],
    tool_choice={"type": "tool", "name": "extract_data"},  # ← форсуй виклик
    messages=[{"role":"user","content": text}]
)
data = next(b.input for b in response.content if b.type=="tool_use")  # гарантований JSON
```

---

## Error Handling & Retries

```python
import anthropic, time

def robust_call(client, **kwargs):
    for attempt in range(3):
        try:
            return client.messages.create(**kwargs)
        except anthropic.RateLimitError:
            wait = int(getattr(e, 'response', {}).headers.get('retry-after', 2 ** attempt))
            time.sleep(wait)
        except anthropic.APIStatusError as e:
            if e.status_code >= 500 and attempt < 2:
                time.sleep(2 ** attempt); continue
            raise
    raise Exception("Max retries exceeded")
```

---

## Message Batches з Tool Use

Поєднання Batch API (50% знижка) з tool use для масової структурованої екстракції:

```python
batch = client.messages.batches.create(requests=[
    {"custom_id": f"doc-{i}", "params": {
        "model": MODEL, "max_tokens": 1024,
        "tools": [extract_tool],
        "tool_choice": {"type": "tool", "name": "extract_data"},
        "messages": [{"role":"user","content": doc}]
    }} for i, doc in enumerate(documents)
])
# 10000 документів → структурований JSON, за півціни, асинхронно
```
