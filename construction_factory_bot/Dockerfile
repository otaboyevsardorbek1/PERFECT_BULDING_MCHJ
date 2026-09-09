# ============================================================
# 🏗️ Qurilish Korxonasi — yagona konteyner
# (FastAPI REST API + Node.js web frontend + Telegram bot)
#
# Build:
#   docker build -t construction-factory-bot .
#
# Run (bitta konteyner — API + web):
#   docker run -p 8000:8000 -p 3000:3000 \
#     -e BOT_TOKEN=... -e ADMIN_IDS=... \
#     construction-factory-bot
#
# Bot alohida jarayon sifatida (yoki docker-compose'da) ishga tushadi:
#   docker exec <container> python main.py
# ============================================================
FROM python:3.11-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1

# Node.js (web frontend uchun) — bookworm repodan
RUN apt-get update && apt-get install -y --no-install-recommends curl ca-certificates \
    && curl -fsSL https://deb.nodesource.com/setup_20.x | bash - \
    && apt-get install -y --no-install-recommends nodejs \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Kutubxonalar (dastlab alohida COPY — kesh samaradorligi uchun)
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

# Loyiha fayllari
COPY . .

# Ishchi papkalar (config.py ularni avtomatik yaratadi ham)
RUN mkdir -p logs reports/excel reports/charts backups static/uploads

# API porti (FastAPI) va web porti (Node.js)
EXPOSE 8000 3000

# Default: FastAPI REST API (docker-compose'da web va bot ham ishga tushadi)
CMD ["sh", "-c", "python -m uvicorn dashboard.app:app --host 0.0.0.0 --port ${PORT:-8000}"]