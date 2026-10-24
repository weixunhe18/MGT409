# Supplier Whisperer, always-on mailbox on Fly.io (see docs/deploy_fly.md).
# The app needs only the standard library plus certifi, so the image stays small.
FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    WHISPERER_DB=/data/sample-mailbox.db

WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt

COPY . .

# Non-root user for the app. The entrypoint starts as root only to hand the Fly volume (/data, mounted
# root-owned) to that user, then drops privileges before Python starts.
RUN useradd --create-home --uid 10001 whisperer \
    && mkdir -p /data \
    && chown -R whisperer:whisperer /app /data \
    && chmod +x /app/scripts/docker-entrypoint.sh

ENTRYPOINT ["/app/scripts/docker-entrypoint.sh"]
# Private network only: reach the dashboard with `fly proxy 8000` (no public port is defined in fly.toml).
CMD ["python", "app.py", "--live", "--mailbox", "--no-browser", "--fly-private"]
