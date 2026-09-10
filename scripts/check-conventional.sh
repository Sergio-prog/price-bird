#!/usr/bin/env sh
set -eu
types='build|chore|ci|docs|feat|fix|perf|refactor|revert|style|test'
header="^($types)(\([a-z0-9._/-]+\))?!?: [^ ].*$"
branch="^($types)/[a-z0-9._-]+$"
status=0

if [ -n "${BRANCH:-}" ] && [ "$BRANCH" != "main" ]; then
  if ! printf '%s\n' "$BRANCH" | grep -Eq "$branch"; then
    printf '%s\n' "branch must look like <type>/<kebab-slug>: $BRANCH"
    status=1
  fi
fi

if [ -n "${PR_TITLE:-}" ]; then
  if ! printf '%s\n' "$PR_TITLE" | grep -Eq "$header"; then
    printf '%s\n' "PR title must look like <type>(scope)?: subject: $PR_TITLE"
    status=1
  fi
fi

# A new branch push has an all-zero base. Check its tip, not the entire history.
if [ -n "${HEAD_SHA:-}" ]; then
  git rev-parse --verify "$HEAD_SHA^{commit}" >/dev/null
  case "${BASE_SHA:-}" in
    ''|0000000000000000000000000000000000000000)
      subjects=$(git log -1 --format=%s "$HEAD_SHA") ;;
    *)
      git rev-parse --verify "$BASE_SHA^{commit}" >/dev/null
      subjects=$(git log --format=%s --no-merges "$BASE_SHA..$HEAD_SHA") ;;
  esac
  bad=$(printf '%s\n' "$subjects" | grep -v '^$' | grep -Ev "$header" || true)
  if [ -n "$bad" ]; then
    printf 'Non-conventional commits:\n%s\n' "$bad"
    status=1
  fi
fi
exit "$status"
