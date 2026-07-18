#!/bin/bash
# stop-hook-git-check.sh — Stop-хук: перевірка git-стану наприкінці ходу.
# Єдина відповідальність: перед завершенням ходу переконатися, що (1) нема
# незакомічених/непушених змін і (2) коміти, які підуть на GitHub, будуть там
# Verified. Вердикт по КОЖНОМУ коміту ухвалюється індивідуально (класифікатор
# нижче), а не гуртом — серверні merge-коміти GitHub і коміти ботів не є
# проблемою і не мають зчиняти тривогу.
#
# Канон живе тут: automations/stop-git-check/ (репозиторій). У середовищі
# Claude Code (web) активна копія — ~/.claude/stop-hook-git-check.sh;
# scripts/setup.sh оновлює її з канону (ідемпотентно).
#
# Статуси підпису (%G?): G добрий · U добрий/недовірений ключ · E неможливо
# перевірити локально (ключа нема в keyring — так виглядають серверні підписи
# GitHub) → вважаємо ПРИСУТНІМ і прийнятним; B зіпсований · X/Y прострочений ·
# R відкликаний · N відсутній → НЕ прийнятний (рев'ю Codex C2).
#
# Класифікатор «Unverified?» (для комітів у upstream..HEAD, індивідуально):
#   R1  committer = noreply@anthropic.com і підпис прийнятний → OK (тихо)
#   R2  коміт уже досяжний з origin/main                      → OK (спільна злита
#       історія — її не переписуємо ніколи)
#   R3  committer = noreply@github.com і підпис прийнятний    → OK (створено
#       сервером GitHub: merge/squash через UI чи API; на GitHub Verified)
#   R4  автор/committer *[bot]* і підпис прийнятний           → OK (бот, підписано)
#   R5  решта (без/зіпсований підпис, сторонній committer)    → FIX (справжня
#       проблема: коміт, який на GitHub буде Unverified)
# Тривога (exit 2) — ЛИШЕ коли є хоч один FIX; звіт показує вердикт і причину
# по кожному коміту. Скан завжди ПОВНИЙ (без обрізання — рев'ю Codex C5);
# обмежується лише друк звіту.
#
# Свідомий скоуп (рев'ю Codex C3 — відхилено): класифікатор вмикається лише
# при commit.gpgsign=true. У репозиторії без налаштованого підписування
# «Unverified» на GitHub — норма, і тривога на кожен коміт зробила б хук
# нестерпним. Хук боронить від РЕГРЕСІЙ там, де підписування вже налаштовано.
#
# Тест-режим (для перевірки класифікатора без Stop-події):
#   STOP_HOOK_TEST_RANGE="<base>..<head>" bash stop-hook-git-check.sh < /dev/null
#   (пропускає перевірки чистоти дерева; ганяє лише класифікатор на діапазоні)

# --- Вхід і захист від рекурсії (як у базовій версії хука) ---
input=$(cat)
stop_hook_active=$(echo "$input" | jq -r '.stop_hook_active' 2>/dev/null)
if [[ "$stop_hook_active" = "true" ]]; then
  exit 0
fi

if ! git rev-parse --git-dir >/dev/null 2>&1; then
  exit 0
fi

# Без remote всі поради «запуш» безглузді — виходимо тихо.
if [[ -z "$(git remote)" ]]; then
  exit 0
fi

TEST_RANGE="${STOP_HOOK_TEST_RANGE:-}"

# Підпис присутній і прийнятний? (G/U/E так; N/B/X/Y/R ні — Codex C2)
sig_ok() { case "$1" in G|U|E) return 0 ;; *) return 1 ;; esac; }

# Людське пояснення поганого статусу підпису для звіту R5.
sig_why() {
  case "$1" in
    N) echo "без підпису" ;;
    B) echo "підпис зіпсований/недійсний (B)" ;;
    X|Y) echo "підпис/ключ прострочений ($1)" ;;
    R) echo "ключ підпису відкликано (R)" ;;
    *) echo "статус підпису $1" ;;
  esac
}

# Резолв upstream без зашитого origin (Codex C1):
# 1) налаштований tracking-ref гілки; 2) <remote>/<гілка> (origin першим);
# 3) <remote>/HEAD. Порожній результат = не вдалося.
resolve_upstream() {
  local u r
  u=$(git rev-parse --abbrev-ref --symbolic-full-name '@{upstream}' 2>/dev/null) \
    && { echo "$u"; return 0; }
  for r in origin $(git remote | grep -vx origin); do
    git rev-parse -q --verify "$r/$current_branch" >/dev/null 2>&1 \
      && { echo "$r/$current_branch"; return 0; }
  done
  for r in origin $(git remote | grep -vx origin); do
    git rev-parse -q --verify "$r/HEAD" >/dev/null 2>&1 \
      && { echo "$r/HEAD"; return 0; }
  done
  return 1
}

if [[ -z "$TEST_RANGE" ]]; then
  # --- Незакомічені зміни ---
  if ! git diff --quiet || ! git diff --cached --quiet; then
    echo "There are uncommitted changes in the repository. Please commit and push these changes to the remote branch." >&2
    exit 2
  fi
  # --- Незатрекані файли ---
  untracked_files=$(git ls-files --others --exclude-standard)
  if [[ -n "$untracked_files" ]]; then
    echo "There are untracked files in the repository. Please commit and push these changes to the remote branch." >&2
    exit 2
  fi
fi

current_branch=$(git branch --show-current)

# --- Відірваний HEAD із локальними комітами не пропускаємо мовчки (Codex C4) ---
if [[ -z "$current_branch" && -z "$TEST_RANGE" ]]; then
  detached_base=""
  for r in origin $(git remote | grep -vx origin); do
    for ref in "$r/HEAD" "$r/main" "$r/master"; do
      git rev-parse -q --verify "$ref" >/dev/null 2>&1 && { detached_base="$ref"; break 2; }
    done
  done
  if [[ -n "$detached_base" ]]; then
    ahead=$(git rev-list "$detached_base..HEAD" --count 2>/dev/null || echo 0)
    if [[ "$ahead" -gt 0 ]]; then
      echo "Detached HEAD має $ahead локальних комітів поза $detached_base. Прикріпи їх до гілки (git switch -c <name>) і запуш — інакше вони загубляться." >&2
      exit 2
    fi
  fi
  exit 0
fi

if [[ -n "$current_branch" || -n "$TEST_RANGE" ]]; then
  if [[ -n "$TEST_RANGE" ]]; then
    range="$TEST_RANGE"
    upstream="${TEST_RANGE%%..*}"
  else
    if ! upstream=$(resolve_upstream) || [[ -z "$upstream" ]]; then
      # Fail-closed (Codex C1): невизначений upstream не означає «все гаразд».
      echo "Не вдалося визначити upstream для '$current_branch' (remote без origin/HEAD?). Перевір вручну, що всі коміти запушені." >&2
      exit 2
    fi
    range="$upstream..HEAD"
  fi

  # --- Індивідуальна перевірка «чи буде Unverified на GitHub» ---
  # Ганяємо, коли ввімкнено підписування комітів (або в тест-режимі) — див.
  # «Свідомий скоуп» у шапці.
  if [[ "$(git config --type=bool commit.gpgsign 2>/dev/null)" == "true" || -n "$TEST_RANGE" ]]; then
    have_main=0
    git rev-parse -q --verify origin/main >/dev/null 2>&1 && have_main=1

    report=""
    actionable=0
    reported=0
    REPORT_MAX=40
    # Скан ПОВНИЙ — жодного обрізання діапазону (Codex C5).
    while IFS='|' read -r h sig ce an; do
      [[ -z "$h" ]] && continue
      # %G? для SSH-підписів без allowedSignersFile/ключа повертає N навіть для
      # ПІДПИСАНОГО коміта. Первинний факт — заголовок gpgsig в об'єкті коміта:
      # якщо він є, статус насправді E (підпис присутній, локально неперевірний).
      if [[ "$sig" == "N" ]] && git cat-file commit "$h" 2>/dev/null | grep -q '^gpgsig'; then
        sig="E"
      fi
      verdict="" ; reason=""
      if [[ "$ce" == "noreply@anthropic.com" ]] && sig_ok "$sig"; then
        continue   # R1: наш із прийнятним підписом — поза підозрою, не звітуємо
      elif [[ $have_main -eq 1 ]] && git merge-base --is-ancestor "$h" origin/main 2>/dev/null; then
        verdict="OK"; reason="R2: уже в origin/main — спільна злита історія, не переписуємо"
      elif [[ "$ce" == "noreply@github.com" ]] && sig_ok "$sig"; then
        verdict="OK"; reason="R3: створено сервером GitHub (merge/squash через UI/API) — на GitHub Verified"
      elif [[ ( "$an" == *"[bot]"* || "$ce" == *"[bot]"* ) ]] && sig_ok "$sig"; then
        verdict="OK"; reason="R4: коміт бота ($an), підписаний — на GitHub Verified"
      else
        verdict="FIX"; reason="R5: $(sig_why "$sig"), committer $ce — на GitHub буде Unverified"
        actionable=$((actionable+1))
      fi
      if [[ $reported -lt $REPORT_MAX ]]; then
        report+="  $h  $verdict  — $reason"$'\n'
        reported=$((reported+1))
      fi
    done < <(git log --format='%h|%G?|%ce|%an' "$range" 2>/dev/null)

    if [[ $actionable -gt 0 ]]; then
      echo "Unverified-коміти на '${current_branch:-$range}' — індивідуальні вердикти по $range:" >&2
      printf '%s' "$report" >&2
      [[ $reported -ge $REPORT_MAX ]] && echo "  … звіт обрізано до $REPORT_MAX рядків (перевірено ВСІ коміти діапазону)." >&2
      echo "Дій лише щодо FIX-комітів: git config user.email noreply@anthropic.com && git config user.name Claude; далі 'git commit --amend --no-edit --reset-author' (верхній коміт) або 'git rebase --exec \"git commit --amend --no-edit --reset-author\" $upstream' (глибші), потім push. OK-коміти НЕ чіпати." >&2
      exit 2
    fi
    # Якщо всі вердикти OK — тривоги нема; у тест-режимі покажемо звіт на stdout.
    if [[ -n "$TEST_RANGE" && -n "$report" ]]; then
      printf '%s' "$report"
    fi
  fi

  if [[ -z "$TEST_RANGE" ]]; then
    # --- Непушені коміти (fail-closed: помилка підрахунку ≠ «нуль») ---
    if ! unpushed=$(git rev-list "$upstream..HEAD" --count 2>/dev/null); then
      echo "Не вдалося порахувати непушені коміти відносно $upstream — перевір вручну." >&2
      exit 2
    fi
    if [[ "$unpushed" -gt 0 ]]; then
      if [[ "$upstream" == *"/$current_branch" ]]; then
        echo "There are $unpushed unpushed commit(s) on branch '$current_branch'. Please push these changes to the remote repository." >&2
      else
        echo "Branch '$current_branch' has $unpushed unpushed commit(s) and no remote branch. Please push these changes to the remote repository." >&2
      fi
      exit 2
    fi
  fi
fi

exit 0
