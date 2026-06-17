#!/usr/bin/env sh
set -eux

USERNAME="${ADMIN_USER:-admin}"
PASSWORD="${ADMIN_PASSWORD:-admin}"

# If user already exists, do nothing
if id "$USERNAME" >/dev/null 2>&1; then
    echo "User '$USERNAME' already exists, skipping creation."
    exit 0
fi

# Debian/Ubuntu (apt-get)
if command -v apt-get >/dev/null 2>&1; then
    export DEBIAN_FRONTEND=noninteractive
    apt-get update
    apt-get install -y --no-install-recommends \
        bash \
        passwd \
        ca-certificates
    rm -rf /var/lib/apt/lists/*

    useradd -m -s /bin/bash "$USERNAME"
    echo "$USERNAME:$PASSWORD" | chpasswd

# Alpine (apk)
elif command -v apk >/dev/null 2>&1; then
    # shadow provides 'chpasswd' and password tools
    apk add --no-cache \
        bash \
        shadow \
        ca-certificates

    adduser -D -s /bin/bash "$USERNAME"
    echo "$USERNAME:$PASSWORD" | chpasswd

else
    echo "Unsupported base image: no apt-get or apk found."
    exit 1
fi

echo "User '$USERNAME' created with shell /bin/bash."
