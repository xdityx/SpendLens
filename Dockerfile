FROM node:20-bookworm-slim AS frontend-builder

WORKDIR /frontend

COPY frontend/package*.json ./
RUN npm ci

COPY frontend/ ./
RUN npm run build && npm prune --omit=dev

FROM python:3.12-slim AS runtime

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV NODE_ENV=production

WORKDIR /app

COPY backend/requirements.txt ./backend/requirements.txt
RUN pip install --no-cache-dir -r backend/requirements.txt

COPY backend/ ./backend/
COPY --from=frontend-builder /usr/local/bin/node /usr/local/bin/node
COPY --from=frontend-builder /frontend/package*.json ./frontend/
COPY --from=frontend-builder /frontend/node_modules ./frontend/node_modules/
COPY --from=frontend-builder /frontend/.next ./frontend/.next/
COPY deploy/start-railway-free.sh ./deploy/start-railway-free.sh

RUN chmod +x ./deploy/start-railway-free.sh

EXPOSE 3000

CMD ["/app/deploy/start-railway-free.sh"]
