#!/usr/bin/env bash
set -euo pipefail

APP_DIR="${APP_DIR:-/opt/projects/HUGEGONGZHONGHAO}"
REPO_URL="${REPO_URL:-https://github.com/regalhu/HUGEGONGZHONGHAO.git}"
SERVICE_NAME="huge-catering"

if [ "$(id -u)" -ne 0 ]; then
  echo "Please run as root: sudo bash deploy/tianyi/repair_public_access.sh"
  exit 1
fi

echo "== Repairing Huge Catering public access =="

apt-get update
apt-get install -y python3 python3-venv python3-pip git nginx curl

git config --global --add safe.directory "$APP_DIR" 2>/dev/null || true

if [ ! -d "$APP_DIR/.git" ]; then
  if [ -f "$APP_DIR/pyproject.toml" ] && [ -d "$APP_DIR/src" ]; then
    echo "Using existing app directory: $APP_DIR"
  else
    rm -rf "$APP_DIR"
    git clone "$REPO_URL" "$APP_DIR"
  fi
else
  git -C "$APP_DIR" pull --ff-only
fi

python3 -m venv "$APP_DIR/.venv"
"$APP_DIR/.venv/bin/python" -m pip install --upgrade pip
"$APP_DIR/.venv/bin/python" -m pip install -r "$APP_DIR/requirements.txt"

if [ ! -f "$APP_DIR/.env" ]; then
  cp "$APP_DIR/.env.example" "$APP_DIR/.env"
fi

grep -q '^WEB_HOST=' "$APP_DIR/.env" && sed -i 's/^WEB_HOST=.*/WEB_HOST=127.0.0.1/' "$APP_DIR/.env" || echo 'WEB_HOST=127.0.0.1' >> "$APP_DIR/.env"
grep -q '^WEB_PORT=' "$APP_DIR/.env" && sed -i 's/^WEB_PORT=.*/WEB_PORT=8766/' "$APP_DIR/.env" || echo 'WEB_PORT=8766' >> "$APP_DIR/.env"
grep -q '^ENABLE_TREND_CONTENT=' "$APP_DIR/.env" && sed -i 's/^ENABLE_TREND_CONTENT=.*/ENABLE_TREND_CONTENT=true/' "$APP_DIR/.env" || echo 'ENABLE_TREND_CONTENT=true' >> "$APP_DIR/.env"

mkdir -p "$APP_DIR/data" "$APP_DIR/outputs" "$APP_DIR/logs"
chown -R root:root "$APP_DIR"
chown -R www-data:www-data "$APP_DIR/data" "$APP_DIR/outputs" "$APP_DIR/logs"
touch "$APP_DIR/data/token_cache.json"
chown www-data:www-data "$APP_DIR/data/token_cache.json"

cp "$APP_DIR/deploy/tianyi/$SERVICE_NAME.service" "/etc/systemd/system/$SERVICE_NAME.service"
cp "$APP_DIR/deploy/tianyi/nginx-huge-catering.conf" /etc/nginx/sites-available/huge-catering.conf
ln -sf /etc/nginx/sites-available/huge-catering.conf /etc/nginx/sites-enabled/huge-catering.conf
rm -f /etc/nginx/sites-enabled/default
for enabled_site in /etc/nginx/sites-enabled/*; do
  [ -e "$enabled_site" ] || continue
  [ "$(basename "$enabled_site")" = "huge-catering.conf" ] && continue
  target="$(readlink -f "$enabled_site" 2>/dev/null || printf '%s' "$enabled_site")"
  if grep -Eq 'listen[[:space:]]+80' "$target" 2>/dev/null && grep -Eq 'server_name[[:space:]]+_' "$target" 2>/dev/null; then
    echo "Disabling conflicting nginx site: $enabled_site"
    rm -f "$enabled_site"
  fi
done

if command -v ufw >/dev/null 2>&1 && ufw status | grep -q "Status: active"; then
  ufw allow 80/tcp
  ufw allow 3389/tcp
fi

nginx -t
systemctl daemon-reload
systemctl enable "$SERVICE_NAME"
systemctl restart "$SERVICE_NAME"
systemctl enable nginx
systemctl restart nginx

sleep 3
curl -fsS http://127.0.0.1:8766/health
echo
curl -fsS http://127.0.0.1/health
echo
curl -fsS http://127.0.0.1:3389/health
echo

PUBLIC_IP="$(curl -fsS --max-time 5 https://api.ipify.org 2>/dev/null || hostname -I | awk '{print $1}')"
echo "Repair complete."
echo "Open: http://$PUBLIC_IP/"
echo "Alternate open: http://$PUBLIC_IP:3389/"
