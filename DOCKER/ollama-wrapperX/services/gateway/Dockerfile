FROM python:3.12-slim

ARG ADMIN_USER=admin
ARG ADMIN_PASSWORD=admin
ENV ADMIN_USER=${ADMIN_USER}
ENV ADMIN_PASSWORD=${ADMIN_PASSWORD}

# Base working directory
WORKDIR /app

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
# Install Python dependencies
# -------------------------------------------------------------------
COPY backend/gateway/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# -------------------------------------------------------------------
# Copy the ENTIRE gateway folder into /app (flat level)
# This ensures main.py, extended/, templates/, etc. all exist in /app
# -------------------------------------------------------------------
COPY backend/gateway/*        /app/
COPY backend/gateway/lib      /app/lib
COPY backend/gateway/extended /app/extended

# If there are other subfolders (templates, static, scripts, etc.), add:
# COPY backend/gateway/templates /app/templates
# COPY backend/gateway/static /app/static
# COPY backend/gateway/scripts /app/scripts

# -------------------------------------------------------------------
# Keep working directory at /app so that:
#  - main.py is at /app/main.py
#  - extended/ is at /app/extended
#  - imports like "from extended import foo" work
# -------------------------------------------------------------------
WORKDIR /app

EXPOSE 8000

# -------------------------------------------------------------------
#
# -------------------------------------------------------------------
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
