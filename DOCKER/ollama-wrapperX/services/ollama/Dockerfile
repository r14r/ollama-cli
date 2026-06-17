FROM ollama/ollama:latest

ARG ADMIN_USER=admin
ARG ADMIN_PASSWORD=admin
ENV ADMIN_USER=${ADMIN_USER}
ENV ADMIN_PASSWORD=${ADMIN_PASSWORD}

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
RUN printf '%s:%s\n' "${ADMIN_USER}" "${ADMIN_PASSWORD}" | chpasswd
