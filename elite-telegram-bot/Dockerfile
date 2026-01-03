# ---- Base image ----
FROM python:3.11-slim

# ---- System deps ----
RUN apt-get update \
    && apt-get install -y --no-install-recommends build-essential \
    && rm -rf /var/lib/apt/lists/*

# ---- Workdir ----
WORKDIR /app

# ---- Python deps ----
COPY pyproject.toml .
RUN pip install --no-cache-dir .
# ---- App code ----
COPY . .

# ---- Entrypoint ----
COPY entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

EXPOSE 8080

ENTRYPOINT ["/bin/sh", "/entrypoint.sh"]
