#!/usr/bin/env bash
set -euo pipefail

APP_DIR="${APP_DIR:-/opt/projects/HUGEGONGZHONGHAO}"
LEGACY_APP_DIR="${LEGACY_APP_DIR:-/opt/huge-catering}"
REPO_URL="${REPO_URL:-https://github.com/regalhu/HUGEGONGZHONGHAO.git}"
BRANCH="${BRANCH:-main}"
SERVICE_NAME="${SERVICE_NAME:-huge-catering}"
PUBLIC_ALT_PORT="${PUBLIC_ALT_PORT:-3389}"
SNAPSHOT_DIR="${SNAPSHOT_DIR:-/root/huge-catering-reset-snapshot-$(date +%Y%m%d-%H%M%S)}"

if [ "$(id -u)" -ne 0 ]; then
  echo "Please run as root: sudo bash deploy/tianyi/reset_and_redeploy.sh"
  exit 1
fi

find_source_dir() {
  local dir="$PWD"
  while [ "$dir" != "/" ]; do
    if [ -f "$dir/pyproject.toml" ] && [ -d "$dir/src/huge_catering" ]; then
      printf '%s\n' "$dir"
      return 0
    fi
    dir="$(dirname "$dir")"
  done
  return 1
}

SOURCE_DIR="$(find_source_dir || true)"
STAGED_SOURCE=""
if [ -n "$SOURCE_DIR" ]; then
  STAGED_SOURCE="/tmp/huge-catering-source-$$"
  mkdir -p "$STAGED_SOURCE"
  tar \
    --exclude='.git' \
    --exclude='.venv' \
    --exclude='.env' \
    --exclude='__pycache__' \
    --exclude='data' \
    --exclude='outputs' \
    --exclude='logs' \
    -C "$SOURCE_DIR" -cf - . | tar -C "$STAGED_SOURCE" -xf -
  echo "Staged source from $SOURCE_DIR to $STAGED_SOURCE"
fi

echo "== Snapshotting current server state to $SNAPSHOT_DIR =="
mkdir -p "$SNAPSHOT_DIR"
systemctl status "$SERVICE_NAME" --no-pager > "$SNAPSHOT_DIR/${SERVICE_NAME}.status.txt" 2>&1 || true
systemctl status nginx --no-pager > "$SNAPSHOT_DIR/nginx.status.txt" 2>&1 || true
ss -ltnp > "$SNAPSHOT_DIR/listeners.txt" 2>&1 || true
ufw status verbose > "$SNAPSHOT_DIR/ufw.status.txt" 2>&1 || true
cp -a "/etc/systemd/system/${SERVICE_NAME}.service" "$SNAPSHOT_DIR/" 2>/dev/null || true
cp -a "/etc/nginx/sites-available/${SERVICE_NAME}.conf" "$SNAPSHOT_DIR/" 2>/dev/null || true
cp -a "$APP_DIR/.env" "$SNAPSHOT_DIR/.env" 2>/dev/null || true
cp -a "$LEGACY_APP_DIR/.env" "$SNAPSHOT_DIR/legacy.env" 2>/dev/null || true

echo "== Stopping and disabling old services =="
systemctl stop "$SERVICE_NAME" 2>/dev/null || true
systemctl disable "$SERVICE_NAME" 2>/dev/null || true
systemctl stop nginx 2>/dev/null || true
if systemctl list-unit-files docker.service >/dev/null 2>&1; then
  systemctl stop docker 2>/dev/null || true
  systemctl disable docker 2>/dev/null || true
fi

echo "== Removing old app, service, and nginx config =="
rm -rf /opt/projects/*
rm -rf "$LEGACY_APP_DIR"
rm -f "/etc/systemd/system/${SERVICE_NAME}.service"
rm -f "/etc/nginx/sites-available/${SERVICE_NAME}.conf"
rm -f "/etc/nginx/sites-enabled/${SERVICE_NAME}.conf"
rm -f /etc/nginx/sites-enabled/default
systemctl daemon-reload

echo "== Removing Docker containers and images if Docker is available =="
if command -v docker >/dev/null 2>&1; then
  docker ps -aq | xargs -r docker rm -f || true
  docker images -aq | xargs -r docker rmi -f || true
fi

echo "== Resetting UFW while keeping SSH and web ports open =="
if command -v ufw >/dev/null 2>&1; then
  ufw --force reset
  ufw allow 22/tcp
  ufw allow 80/tcp
  ufw allow 443/tcp
  if [ -n "$PUBLIC_ALT_PORT" ]; then
    ufw allow "${PUBLIC_ALT_PORT}/tcp"
  fi
  ufw --force enable
  systemctl enable ufw 2>/dev/null || true
  systemctl restart ufw 2>/dev/null || true
fi

echo "== Restoring source and redeploying =="
mkdir -p "$APP_DIR"
if [ -n "$STAGED_SOURCE" ]; then
  tar -C "$STAGED_SOURCE" -cf - . | tar -C "$APP_DIR" -xf -
else
  rm -rf "$APP_DIR"
  git clone --branch "$BRANCH" "$REPO_URL" "$APP_DIR" || git clone "$REPO_URL" "$APP_DIR"
fi
if [ -f "$SNAPSHOT_DIR/.env" ]; then
  cp "$SNAPSHOT_DIR/.env" "$APP_DIR/.env"
elif [ -f "$SNAPSHOT_DIR/legacy.env" ]; then
  cp "$SNAPSHOT_DIR/legacy.env" "$APP_DIR/.env"
fi

cd "$APP_DIR"
SKIP_GIT_PULL=1 APP_DIR="$APP_DIR" LEGACY_APP_DIR="$LEGACY_APP_DIR" SERVICE_NAME="$SERVICE_NAME" PUBLIC_ALT_PORT="$PUBLIC_ALT_PORT" bash deploy.sh

echo "== Final status =="
systemctl is-active "$SERVICE_NAME"
systemctl is-active nginx
curl -fsS http://127.0.0.1/health
echo
if [ -n "$PUBLIC_ALT_PORT" ]; then
  curl -fsS "http://127.0.0.1:${PUBLIC_ALT_PORT}/health"
  echo
fi
echo "Snapshot: $SNAPSHOT_DIR"
