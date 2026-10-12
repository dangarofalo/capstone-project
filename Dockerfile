# SentinelView server image: builds the React dashboard, then runs the FastAPI server
# that serves both the API and the dashboard.

# --- Stage 1: build the dashboard -------------------------------------------------
FROM node:24-alpine AS dashboard
WORKDIR /build/frontend
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci --no-audit --no-fund
COPY frontend/ ./
RUN npm run build

# --- Stage 2: the server ----------------------------------------------------------
FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /app/backend
COPY backend/requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt
COPY backend/app ./app
COPY --from=dashboard /build/frontend/dist /app/frontend/dist

# Don't run as root inside the container.
RUN useradd --system --uid 1000 sentinel
USER sentinel

EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=5s \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/api/health')"
# --proxy-headers: trust Caddy's X-Forwarded-* headers so the app knows requests were HTTPS.
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--proxy-headers", "--forwarded-allow-ips", "*"]
