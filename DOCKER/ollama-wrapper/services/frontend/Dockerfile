FROM python:3.11-slim

ARG ADMIN_USER=admin
ARG ADMIN_PASSWORD=admin
ENV ADMIN_USER=${ADMIN_USER}
ENV ADMIN_PASSWORD=${ADMIN_PASSWORD}

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

COPY frontend/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# -------------------------------------------------------------------
# copy and start app
# -------------------------------------------------------------------
COPY frontend/ .
CMD ["streamlit", "run", "Home.py", "--server.port", "8501", "--server.address", "0.0.0.0"]
