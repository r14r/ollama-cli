#!/bin/sh
set -euo pipefail

if [ -z "${ADMIN_USER:-}" ] || [ -z "${ADMIN_PASSWORD:-}" ]; then
  echo "ADMIN_USER and ADMIN_PASSWORD must be provided"
  exit 1
fi

mkdir -p /tmp/prometheus
chmod 0777 /tmp/prometheus

cat <<EOF >/tmp/prometheus/web-config.yml
basic_auth_users:
  ${ADMIN_USER}: ${ADMIN_PASSWORD}
EOF

exec gosu prometheus /bin/prometheus "$@" \
  --config.file=/tmp/prometheus/prometheus.yml \
  --web.config.file=/tmp/prometheus/web-config.yml
