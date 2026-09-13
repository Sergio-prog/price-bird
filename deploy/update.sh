#!/usr/bin/env sh
set -eu

main() {
  cd "$(dirname "$0")/.."
  git fetch -q origin main
  git checkout -q main
  git pull -q --ff-only origin main

  docker compose build bot worker migrate
  docker compose run --rm migrate
  docker compose up -d --no-build --remove-orphans bot worker

  sleep 2
  for _ in 1 2 3 4 5 6 7 8 9 10; do
    running=$(docker compose ps --services --status running)
    if printf '%s\n' "$running" | grep -qx bot && printf '%s\n' "$running" | grep -qx worker; then
      echo "deployed $(git rev-parse --short HEAD), bot and worker running"
      docker compose ps bot worker
      exit 0
    fi
    sleep 2
  done

  echo "bot or worker did not stay running after deploy"
  docker compose ps bot worker
  docker compose logs --tail=30 bot worker || true
  exit 1
}

main "$@"
