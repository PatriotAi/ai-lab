# End-to-End Testing Patterns

## Full User Flow

```python
def test_signup_to_purchase(page):
    # 1. Реєстрація
    page.goto("http://localhost:3000/signup")
    page.fill("[data-testid=email]", "test@example.com")
    page.fill("[data-testid=password]", "SecurePass123")
    page.click("[data-testid=submit]")
    page.wait_for_url("**/dashboard")

    # 2. Додавання в кошик
    page.goto("http://localhost:3000/products")
    page.click("[data-testid=product-1] >> text=Add to Cart")
    expect(page.locator("[data-testid=cart-count]")).to_have_text("1")

    # 3. Checkout
    page.click("[data-testid=checkout]")
    page.fill("[data-testid=card]", "4242424242424242")
    page.click("[data-testid=pay]")
    expect(page.locator("[data-testid=success]")).to_be_visible()
```

---

## Network Mocking

```python
# Підмінь API-відповіді — тестуй без реального бекенду
def test_with_mocked_api(page):
    page.route("**/api/users", lambda route: route.fulfill(
        status=200,
        content_type="application/json",
        body='[{"id":1,"name":"Test User"}]'
    ))
    page.goto("http://localhost:3000/users")
    expect(page.locator("text=Test User")).to_be_visible()

# Симуляція помилки сервера
def test_api_error_handling(page):
    page.route("**/api/data", lambda route: route.fulfill(status=500))
    page.goto("http://localhost:3000")
    expect(page.locator("[data-testid=error-banner]")).to_be_visible()
```

---

## Test Data Factories

```python
import uuid

def make_user(**overrides):
    return {
        "id": str(uuid.uuid4()),
        "email": f"user-{uuid.uuid4().hex[:8]}@test.com",
        "name": "Test User",
        "role": "member",
        **overrides  # перевизнач що треба
    }

# Використання:
admin = make_user(role="admin")
banned = make_user(status="banned")
```

Фабрики дають унікальні дані для кожного тесту → немає конфліктів між прогонами.

---

## Parallel Test Execution

```python
# pytest-playwright: паралельні воркери
# pytest -n 4 --browser chromium

# Кожен тест ізольований — свій browser context
def test_isolated(browser):
    context = browser.new_context()  # чистий стан
    page = context.new_page()
    # ... тест
    context.close()  # прибирання
```

---

## Waiting Strategies (анти-flaky)

```python
# ✗ Жорсткий sleep — flaky і повільно
time.sleep(3)

# ✓ Чекай конкретну умову
page.wait_for_selector("[data-testid=loaded]")
page.wait_for_load_state("networkidle")
expect(page.locator(".spinner")).to_be_hidden()

# ✓ Auto-retry assertions (Playwright чекає до timeout)
expect(page.locator("text=Success")).to_be_visible(timeout=10000)
```

---

## Visual Regression (детальніше)

```python
# Playwright має вбудоване порівняння скриншотів
def test_visual(page):
    page.goto("http://localhost:3000")
    # Перший прогон створює baseline, наступні порівнюють
    expect(page).to_have_screenshot("homepage.png", max_diff_pixels=100)

# Маскуй динамічні елементи (час, рандом)
expect(page).to_have_screenshot("page.png", mask=[page.locator(".timestamp")])
```

---

## Performance Testing

```python
def test_page_performance(page):
    page.goto("http://localhost:3000")
    metrics = page.evaluate("""() => {
        const nav = performance.getEntriesByType('navigation')[0];
        return {
            loadTime: nav.loadEventEnd - nav.fetchStart,
            domReady: nav.domContentLoadedEventEnd - nav.fetchStart,
            firstPaint: performance.getEntriesByName('first-contentful-paint')[0]?.startTime
        };
    }""")
    assert metrics["loadTime"] < 3000, f"Load too slow: {metrics['loadTime']}ms"
    assert metrics["firstPaint"] < 1500, f"FCP too slow"
```

---

## Accessibility (детальніше)

```python
# axe-core через CDN injection
def test_a11y(page):
    page.goto("http://localhost:3000")
    page.add_script_tag(url="https://cdnjs.cloudflare.com/ajax/libs/axe-core/4.8.2/axe.min.js")
    results = page.evaluate("async () => await axe.run()")
    violations = results["violations"]
    critical = [v for v in violations if v["impact"] == "critical"]
    assert len(critical) == 0, f"Critical a11y issues: {[v['id'] for v in critical]}"
```
