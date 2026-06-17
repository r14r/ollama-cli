# Monitoring

This folder keeps high-level notes for the Prometheus + Grafana stack that ships with v3.

- Prometheus reads `/metrics` from the gateway and the `frontend` UI (see `../prometheus/prometheus.yml`) and also leverages `ADMIN_USER`/`ADMIN_PASSWORD` to protect the web UI.
- Grafana is pre-provisioned with a Prometheus datasource (`../grafana/provisioning/datasource.yml`).
- Metrics for prompts, request counts, and latency are exposed by the gateway.
- Use `docker compose -f docker/docker-compose.yml up` to see dashboards on http://localhost:3000 and Prometheus on http://localhost:9090.
