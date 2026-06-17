FROM prom/prometheus:latest

ARG ADMIN_USER=admin
ARG ADMIN_PASSWORD=admin
ENV ADMIN_USER=${ADMIN_USER}
ENV ADMIN_PASSWORD=${ADMIN_PASSWORD}

USER root

# -------------------------------------------------------------------
# install bash + passwd support
# -------------------------------------------------------------------
COPY services/add-bash.sh /usr/local/bin/add-bash.sh
RUN chmod +x /usr/local/bin/add-bash.sh && /usr/local/bin/add-bash.sh

# -------------------------------------------------------------------
# install gosu (needed for entrypoint)
# -------------------------------------------------------------------
RUN if command -v apt-get >/dev/null 2>&1; then \
      apt-get update && apt-get install -y --no-install-recommends gosu && rm -rf /var/lib/apt/lists/*; \
    elif command -v apk >/dev/null 2>&1; then \
      apk add --no-cache --repository=http://dl-cdn.alpinelinux.org/alpine/edge/testing gosu; \
    fi

# -------------------------------------------------------------------
# add admin user
# -------------------------------------------------------------------
COPY services/add-admin-user.sh /usr/local/bin/add-admin-user.sh
RUN chmod +x /usr/local/bin/add-admin-user.sh && /usr/local/bin/add-admin-user.sh

RUN set -eux; \
    if ! id prometheus >/dev/null 2>&1; then \
        echo 'prometheus:x:1000:1000:Prometheus user:/tmp/prometheus:/bin/false' >> /etc/passwd; \
        echo 'prometheus:x:1000:' >> /etc/group; \
    fi

# -------------------------------------------------------------------
# copy and start app
# -------------------------------------------------------------------
RUN mkdir -p /tmp/prometheus && chown prometheus:prometheus /tmp/prometheus
COPY --chmod=0755 services/prometheus/start.sh /tmp/prometheus/start.sh

ENTRYPOINT ["/tmp/prometheus/start.sh"]
