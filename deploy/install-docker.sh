#!/usr/bin/env bash
set -euo pipefail

if [[ "$(id -u)" -ne 0 ]]; then
    echo "Запустите скрипт через sudo: sudo bash deploy/install-docker.sh" >&2
    exit 1
fi

apt-get update
apt-get install -y docker.io docker-compose-v2
systemctl enable --now docker
docker --version
docker compose version
