#!/usr/bin/env bash
set -euo pipefail

APP_DIR="${APP_DIR:-/opt/huge-catering}"
REPO_URL="${REPO_URL:-https://github.com/regalhu/HUGEGONGZHONGHAO.git}"
SERVICE_NAME="huge-catering"

if [ "$(id -u)" -ne 0 ]; then
  echo "Please run as root: sudo bash deploy/tianyi/deploy_ubuntu.sh"
  exit 1
fi

apt-get update
apt-get install -y python3 python3-venv python3-pip git nginx

if [ ! -d "$APP_DIR/.git" ]; then
  rm -rf "$APP_DIR"
  git clone "$REPO_URL" "$APP_DIR"
else
  git -C "$APP_DIR" pull --ff-only
fi

python3 -m venv "$APP_DIR/.venv"
"$APP_DIR/.venv/bin/python" -m pip install --upgrade pip
"$APP_DIR/.venv/bin/python" -m pip install -r "$APP_DIR/requirements.txt"

if [ ! -f "$APP_DIR/.env" ]; then
  cp "$APP_DIR/.env.example" "$APP_DIR/.env"
  echo "Created $APP_DIR/.env. Edit it before starting uploads."
fi

chown -R www-data:www-data "$APP_DIR"
cp "$APP_DIR/deploy/tianyi/$SERVICE_NAME.service" "/etc/systemd/system/$SERVICE_NAME.service"
cp "$APP_DIR/deploy/tianyi/nginx-huge-catering.conf" /etc/nginx/sites-available/huge-catering.conf
ln -sf /etc/nginx/sites-available/huge-catering.conf /etc/nginx/sites-enabled/huge-catering.conf
rm -f /etc/nginx/sites-enabled/default

nginx -t
systemctl daemon-reload
systemctl enable "$SERVICE_NAME"
systemctl restart "$SERVICE_NAME"
systemctl reload nginx

echo "Deployment finished."
echo "Service: systemctl status $SERVICE_NAME --no-pager"
echo "Logs: journalctl -u $SERVICE_NAME -f"
