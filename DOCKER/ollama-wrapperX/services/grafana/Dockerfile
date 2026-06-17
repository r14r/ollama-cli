FROM grafana/grafana:latest

ARG ADMIN_USER=admin
ARG ADMIN_PASSWORD=admin
ENV ADMIN_USER=${ADMIN_USER}
ENV ADMIN_PASSWORD=${ADMIN_PASSWORD}

ENV GF_SECURITY_ADMIN_USER=${ADMIN_USER}
ENV GF_SECURITY_ADMIN_PASSWORD=${ADMIN_PASSWORD}

USER root

# -------------------------------------------------------------------
# install bash + passwd support
# -------------------------------------------------------------------
COPY services/add-bash.sh /usr/local/bin/add-bash.sh
RUN chmod +x /usr/local/bin/add-bash.sh && /usr/local/bin/add-bash.sh

# -------------------------------------------------------------------
# add admin user
# -------------------------------------------------------------------
COPY services/add-admin-user.sh /usr/local/bin/add-admin-user.sh
RUN chmod +x /usr/local/bin/add-admin-user.sh && /usr/local/bin/add-admin-user.sh

# -------------------------------------------------------------------
#
# -------------------------------------------------------------------
USER grafana
