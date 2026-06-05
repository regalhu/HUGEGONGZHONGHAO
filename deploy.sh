#!/usr/bin/env bash
set -euo pipefail

APP_DIR="${APP_DIR:-/opt/projects/HUGEGONGZHONGHAO}"
LEGACY_APP_DIR="${LEGACY_APP_DIR:-/opt/huge-catering}"
REPO_URL="${REPO_URL:-https://github.com/regalhu/HUGEGONGZHONGHAO.git}"
BRANCH="${BRANCH:-main}"
SERVICE_NAME="${SERVICE_NAME:-huge-catering}"
APP_PORT="${APP_PORT:-8766}"
PUBLIC_ALT_PORT="${PUBLIC_ALT_PORT:-3389}"
APP_USER="${APP_USER:-www-data}"
APP_GROUP="${APP_GROUP:-www-data}"
NGINX_SITE="/etc/nginx/sites-available/${SERVICE_NAME}.conf"
NGINX_ENABLED="/etc/nginx/sites-enabled/${SERVICE_NAME}.conf"

if [ "$(id -u)" -ne 0 ]; then
  echo "Please run as root: sudo bash deploy.sh"
  exit 1
fi

echo "== Deploying ${SERVICE_NAME} to ${APP_DIR} =="

apt-get update
apt-get install -y git python3 python3-venv python3-pip nginx curl ufw

mkdir -p "$(dirname "$APP_DIR")"

if [ ! -d "$APP_DIR/.git" ]; then
  if [ -f "$APP_DIR/pyproject.toml" ] && [ -d "$APP_DIR/src" ]; then
    echo "Using existing non-git app directory: $APP_DIR"
  else
    rm -rf "$APP_DIR"
    git clone --branch "$BRANCH" "$REPO_URL" "$APP_DIR" || git clone "$REPO_URL" "$APP_DIR"
  fi
else
  if [ "${SKIP_GIT_PULL:-0}" = "1" ]; then
    echo "Skipping git pull because SKIP_GIT_PULL=1"
  else
    git -C "$APP_DIR" fetch origin
    git -C "$APP_DIR" checkout "$BRANCH"
    git -C "$APP_DIR" reset --hard "origin/$BRANCH"
  fi
fi

cd "$APP_DIR"

if [ ! -f .env ] && [ -f "$LEGACY_APP_DIR/.env" ]; then
  cp "$LEGACY_APP_DIR/.env" .env
fi
if [ ! -f .env ]; then
  cp .env.example .env
  echo "Created ${APP_DIR}/.env from .env.example. Fill credentials on the server if uploads are needed."
fi

ensure_env() {
  key="$1"
  value="$2"
  if grep -q "^${key}=" .env; then
    sed -i "s|^${key}=.*|${key}=${value}|" .env
  else
    printf '%s=%s\n' "$key" "$value" >> .env
  fi
}

ensure_env WEB_HOST 0.0.0.0
ensure_env WEB_PORT "$APP_PORT"
ensure_env ENABLE_TREND_CONTENT true

python3 -m venv .venv
".venv/bin/python" -m pip install --upgrade pip
".venv/bin/python" -m pip install -r requirements.txt

mkdir -p data outputs logs
touch data/token_cache.json
chown -R root:root "$APP_DIR"
chown -R "$APP_USER:$APP_GROUP" "$APP_DIR/data" "$APP_DIR/outputs" "$APP_DIR/logs"
chmod 755 "$APP_DIR"

NGINX_ALT_LISTEN=""
if [ -n "$PUBLIC_ALT_PORT" ] && [ "$PUBLIC_ALT_PORT" != "80" ]; then
  NGINX_ALT_LISTEN="    listen ${PUBLIC_ALT_PORT};"
fi

cat > "/etc/systemd/system/${SERVICE_NAME}.service" <<SERVICE
[Unit]
Description=Huge Catering WeChat Article Generator
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
User=${APP_USER}
Group=${APP_GROUP}
WorkingDirectory=${APP_DIR}
EnvironmentFile=-${APP_DIR}/.env
Environment=PYTHONPATH=${APP_DIR}/src
ExecStart=${APP_DIR}/.venv/bin/gunicorn --workers 2 --bind 0.0.0.0:${APP_PORT} huge_catering.wsgi:app
Restart=always
RestartSec=5
TimeoutStartSec=30
KillSignal=SIGQUIT

[Install]
WantedBy=multi-user.target
SERVICE

cat > "$NGINX_SITE" <<NGINX
server {
    listen 80 default_server;
${NGINX_ALT_LISTEN}
    server_name _;

    client_max_body_size 20m;

    location = /health {
        proxy_pass http://127.0.0.1:${APP_PORT}/health;
        proxy_http_version 1.1;
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto \$scheme;
        access_log off;
    }

    location / {
        proxy_pass http://127.0.0.1:${APP_PORT};
        proxy_http_version 1.1;
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto \$scheme;
        proxy_connect_timeout 10s;
        proxy_send_timeout 120s;
        proxy_read_timeout 120s;
    }
}
NGINX

ln -sf "$NGINX_SITE" "$NGINX_ENABLED"
rm -f /etc/nginx/sites-enabled/default
for enabled_site in /etc/nginx/sites-enabled/*; do
  [ -e "$enabled_site" ] || continue
  [ "$enabled_site" = "$NGINX_ENABLED" ] && continue
  target="$(readlink -f "$enabled_site" 2>/dev/null || printf '%s' "$enabled_site")"
  if grep -Eq 'listen[[:space:]]+80' "$target" 2>/dev/null && grep -Eq 'server_name[[:space:]]+_' "$target" 2>/dev/null; then
    echo "Disabling conflicting nginx site: $enabled_site"
    rm -f "$enabled_site"
  fi
done

ufw allow 22/tcp
ufw allow 80/tcp
ufw allow 443/tcp
if [ -n "$PUBLIC_ALT_PORT" ]; then
  ufw allow "${PUBLIC_ALT_PORT}/tcp"
fi
ufw --force enable
systemctl enable ufw
systemctl restart ufw

nginx -t
systemctl daemon-reload
systemctl enable "$SERVICE_NAME"
systemctl restart "$SERVICE_NAME"
systemctl enable nginx
systemctl restart nginx

sleep 3
curl -fsS "http://127.0.0.1:${APP_PORT}/health" >/dev/null
curl -fsS http://127.0.0.1/health >/dev/null
if [ -n "$PUBLIC_ALT_PORT" ] && [ "$PUBLIC_ALT_PORT" != "80" ]; then
  curl -fsS "http://127.0.0.1:${PUBLIC_ALT_PORT}/health" >/dev/null
fi

echo "Deployment finished."
echo "Project dir: $APP_DIR"
echo "Internal app: 0.0.0.0:${APP_PORT}"
echo "External URL: http://113.249.104.188/"
if [ -n "$PUBLIC_ALT_PORT" ] && [ "$PUBLIC_ALT_PORT" != "80" ]; then
  echo "Alternate external URL: http://113.249.104.188:${PUBLIC_ALT_PORT}/"
fi
echo "Logs: journalctl -u ${SERVICE_NAME} -f"
