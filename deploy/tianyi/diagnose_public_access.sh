#!/usr/bin/env bash
set -u

APP_DIR="${APP_DIR:-/opt/projects/HUGEGONGZHONGHAO}"
SERVICE_NAME="huge-catering"

echo "== Huge Catering public access diagnosis =="
date
echo

echo "== Network =="
echo "Public IP: $(curl -fsS --max-time 5 https://api.ipify.org 2>/dev/null || echo unknown)"
hostname -I 2>/dev/null || true
echo

echo "== Ports =="
ss -ltnp 2>/dev/null | grep -E ':(80|3389|8766)\b' || echo "No listener on 80/3389/8766"
echo

echo "== systemd =="
systemctl status "$SERVICE_NAME" --no-pager || true
echo

echo "== nginx =="
nginx -t || true
systemctl status nginx --no-pager || true
echo

echo "== Health checks =="
curl -i --max-time 5 http://127.0.0.1:8766/health || true
echo
curl -i --max-time 5 http://127.0.0.1/health || true
echo
curl -i --max-time 5 http://127.0.0.1:3389/health || true
echo

echo "== Recent app logs =="
journalctl -u "$SERVICE_NAME" -n 80 --no-pager || true
echo

echo "== File permissions =="
ls -ld "$APP_DIR" "$APP_DIR/data" "$APP_DIR/outputs" "$APP_DIR/logs" 2>/dev/null || true
