# LeadSynt — single image, single port (3000).
#
#   docker build -t leadsynt .
#   docker run -p 3000:3000 --env-file .env leadsynt
#
# or simply:  docker compose up --build   (adds SQL Server 2022 + Redis)
#
# The image contains the frontend (Next.js standalone) AND the backend
# (FastAPI + Celery worker + beat). The browser only ever talks to :3000;
# the Next server proxies /api/* to the API on loopback. The API and the
# worker never appear on the public network.

# ---------- 1. build the frontend (standalone output) ----------
FROM node:20-alpine AS frontend-build
WORKDIR /build
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci --no-audit --no-fund
COPY frontend/ ./
ENV NEXT_TELEMETRY_DISABLED=1
# Inside the image the API always lives on loopback:
ENV BACKEND_URL=http://127.0.0.1:8000
RUN npm run build

# ---------- 2. runtime: python (API + jobs) + node (frontend) ----------
FROM python:3.12-slim

# ODBC Driver 18 for Microsoft SQL Server (mssql+pyodbc)
RUN apt-get update && apt-get install -y --no-install-recommends \
        ca-certificates gnupg curl unixodbc \
    && curl -fsSL https://packages.microsoft.com/keys/microsoft.asc \
        | gpg --dearmor -o /usr/share/keyrings/microsoft.gpg \
    && echo "deb [arch=amd64 signed-by=/usr/share/keyrings/microsoft.gpg] https://packages.microsoft.com/deb/$(. /etc/os-release && echo $VERSION_CODENAME)/prod $(. /etc/os-release && echo $VERSION_CODENAME) main" \
        > /etc/apt/sources.list.d/mssql-release.list \
    && apt-get update \
    && ACCEPT_EULA=Y apt-get install -y --no-install-recommends msodbcsql18 \
    && apt-get remove -y gnupg \
    && apt-get clean && rm -rf /var/lib/apt/lists/*

# Node 20 runtime for the Next.js standalone server
RUN apt-get update && apt-get install -y --no-install-recommends curl ca-certificates xz-utils \
    && curl -fsSL https://nodejs.org/dist/v20.18.1/node-v20.18.1-linux-x64.tar.xz -o /tmp/node.tar.xz \
    && tar -xJ -f /tmp/node.tar.xz -C /usr/local --strip-components=1 \
    && rm /tmp/node.tar.xz \
    && apt-get clean && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Backend (production deps only)
COPY backend/requirements.txt ./backend/requirements.txt
RUN pip install --no-cache-dir -r backend/requirements.txt
COPY backend/ ./backend/

# Frontend (standalone: server.js + its node_modules + static assets)
COPY --from=frontend-build /build/.next/standalone ./frontend/
COPY --from=frontend-build /build/.next/static ./frontend/.next/static
COPY --from=frontend-build /build/public ./frontend/public
COPY scripts/docker-entrypoint.sh ./docker-entrypoint.sh
RUN chmod +x ./docker-entrypoint.sh

# Defaults; compose / env file override (see .env.example)
ENV LEADSynt_ENVIRONMENT=production \
    LEADSynt_LOG_JSON=true \
    LEADSynt_DATABASE_URL="mssql+pyodbc://sa:Change%21Me-Strong@db:1433/LeadSynt?driver=ODBC+Driver+18+for+SQL+Server&TrustServerCertificate=yes" \
    LEADSynt_REDIS_URL=redis://redis:6379/0 \
    LEADSynt_CELERY_BROKER_URL=redis://redis:6379/1 \
    LEADSynt_CELERY_RESULT_BACKEND=redis://redis:6379/2

EXPOSE 3000
ENTRYPOINT ["./docker-entrypoint.sh"]
