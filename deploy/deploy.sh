#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/.."

if [[ ! -f .env ]]; then
    echo "Создайте deploy/.env на основе deploy/.env.example." >&2
    exit 1
fi
if [[ ! -s schedule.xls ]]; then
    echo "Скопируйте файл расписания в корень проекта и назовите schedule.xls." >&2
    exit 1
fi

compose=(docker compose --env-file deploy/.env -f deploy/compose.yml)
if ! docker info >/dev/null 2>&1; then
    compose=(sudo docker compose --env-file deploy/.env -f deploy/compose.yml)
fi

"${compose[@]}" up -d --build web caddy
if grep -Eq '^TELEGRAM_BOT_TOKEN=.+$' deploy/.env; then
    "${compose[@]}" --profile bot up -d --build bot
else
    echo "Mini App развернут; бот пропущен, так как TELEGRAM_BOT_TOKEN не задан."
fi

"${compose[@]}" ps
