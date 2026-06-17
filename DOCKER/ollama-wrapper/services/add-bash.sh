#!/bin/sh
set -eux

if [ -x /usr/bin/bash ] && command -v passwd >/dev/null 2>&1 && command -v chpasswd >/dev/null 2>&1; then
  echo "bash + passwd already available"
  exit 0
fi

if command -v apt-get >/dev/null 2>&1; then
  apt-get update
  apt-get install -y --no-install-recommends bash passwd
  rm -rf /var/lib/apt/lists/*
elif command -v apk >/dev/null 2>&1; then
  apk add --no-cache bash passwd shadow
else
  echo "no supported package manager found"
  exit 1
fi
