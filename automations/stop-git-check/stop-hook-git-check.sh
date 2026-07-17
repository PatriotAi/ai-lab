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
# Класифікатор «Unverified?» (для комітів у upstream..HEAD, індивідуально):
#   R1  committer = noreply@anthropic.com і підпис є        → OK (наш підписаний)
#   R2  коміт уже досяжний з origin/main                    → OK (спільна злита
#       історія — її не переписуємо ніколи)
#   R3  committer = noreply@github.com і підпис є           → OK (створено сервером
#       GitHub: merge/squash через UI чи API; GitHub показує такі як Verified)
#   R4  автор/committer *[bot]* і підпис є                  → OK (бот, підписано)
#   R5  інакше (без підпису, або чужий committer)           → FIX (справжня
#       проблема: наш локальний коміт, який на GitHub буде Unverified)
# Тривога (exit 2) — ЛИШЕ коли є хоч один FIX; звіт показує вердикт і причину
# по кожному коміту.
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
if [[ -n "$current_branch" || -n "$TEST_RANGE" ]]; then
  if [[ -n "$TEST_RANGE" ]]; then
    range="$TEST_RANGE"
    upstream="${TEST_RANGE%%..*}"
  else
    if git rev-parse "origin/$current_branch" >/dev/null 2>&1; then
      upstream="origin/$current_branch"
    else
      upstream="origin/HEAD"
    fi
    range="$upstream..HEAD"
  fi

  # --- Індивідуальна перевірка «чи буде Unverified на GitHub» ---
  # Ганяємо, коли ввімкнено підписування комітів (або в тест-режимі).
  if [[ "$(git config --type=bool commit.gpgsign 2>/dev/null)" == "true" || -n "$TEST_RANGE" ]]; then
    have_main=0
    git rev-parse -q --verify origin/main >/dev/null 2>&1 && have_main=1

    report=""
    actionable=0
    # %G?: N = без підпису; G/U/E/B/X/Y/R = підпис присутній (локально може
    # бути неперевірним — E — бо ключа GitHub нема в keyring; це не проблема).
    while IFS='|' read -r h sig ce an; do
      [[ -z "$h" ]] && continue
      verdict="" ; reason=""
      if [[ "$ce" == "noreply@anthropic.com" && "$sig" != "N" ]]; then
        continue   # R1: наш підписаний — поза підозрою, не звітуємо
      elif [[ $have_main -eq 1 ]] && git merge-base --is-ancestor "$h" origin/main 2>/dev/null; then
        verdict="OK"; reason="R2: уже в origin/main — спільна злита історія, не переписуємо"
      elif [[ "$ce" == "noreply@github.com" && "$sig" != "N" ]]; then
        verdict="OK"; reason="R3: створено сервером GitHub (merge/squash через UI/API) — на GitHub Verified"
      elif [[ ( "$an" == *"[bot]"* || "$ce" == *"[bot]"* ) && "$sig" != "N" ]]; then
        verdict="OK"; reason="R4: коміт бота ($an), підписаний — на GitHub Verified"
      else
        verdict="FIX"; reason="R5: без підпису або сторонній committer ($ce) — на GitHub буде Unverified"
        actionable=$((actionable+1))
      fi
      report+="  $h  $verdict  — $reason"$'\n'
    done < <(git log --format='%h|%G?|%ce|%an' "$range" 2>/dev/null | head -200)

    if [[ $actionable -gt 0 ]]; then
      echo "Unverified-коміти на '$current_branch' — індивідуальні вердикти по $range:" >&2
      printf '%s' "$report" >&2
      echo "Дій лише щодо FIX-комітів: git config user.email noreply@anthropic.com && git config user.name Claude; далі 'git commit --amend --no-edit --reset-author' (верхній коміт) або 'git rebase --exec \"git commit --amend --no-edit --reset-author\" $upstream' (глибші), потім push. OK-коміти НЕ чіпати." >&2
      exit 2
    fi
    # Якщо всі вердикти OK — тривоги нема; у тест-режимі покажемо звіт на stdout.
    if [[ -n "$TEST_RANGE" && -n "$report" ]]; then
      printf '%s' "$report"
    fi
  fi

  if [[ -z "$TEST_RANGE" ]]; then
    # --- Непушені коміти ---
    unpushed=$(git rev-list "$upstream..HEAD" --count 2>/dev/null) || unpushed=0
    if [[ "$unpushed" -gt 0 ]]; then
      if [[ "$upstream" == "origin/$current_branch" ]]; then
        echo "There are $unpushed unpushed commit(s) on branch '$current_branch'. Please push these changes to the remote repository." >&2
      else
        echo "Branch '$current_branch' has $unpushed unpushed commit(s) and no remote branch. Please push these changes to the remote repository." >&2
      fi
      exit 2
    fi
  fi
fi

exit 0
