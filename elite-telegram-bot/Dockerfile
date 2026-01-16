# ---- Base image ----
FROM python:3.11-slim

# ---- Environment ----
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

# ---- System deps ----
RUN apt-get update \
    && apt-get install -y --no-install-recommends build-essential curl \
    && rm -rf /var/lib/apt/lists/*

COPY /requirements.txt ./requirements.txt 

# ---- Workdir ----
WORKDIR /app/src
ENV PYTHONPATH=/app/src

# ---- Python deps (COPY FIRST) ----
COPY /requirements.txt  .

RUN pip install --upgrade pip \
    && pip install --no-cache-dir -r requirements.txt

# ---- App code ----
COPY . .

# ---- Entrypoint ----
RUN chmod +x entrypoint.sh

EXPOSE 8080

CMD ["bash", "entrypoint.sh"]
