# Stage 1: build the React frontend into /static
FROM node:22-slim AS frontend
RUN corepack enable
WORKDIR /frontend
COPY frontend/package.json frontend/pnpm-lock.yaml ./
RUN pnpm install --frozen-lockfile
COPY frontend/ ./
RUN pnpm build  # outDir is ../static -> /static

FROM python:3.11-slim

WORKDIR /app
ENV PYTHONUNBUFFERED=1 FASTEMBED_CACHE_PATH=/app/.cache/fastembed

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Descarga el modelo de embeddings en el build para que el arranque sea rápido
RUN python -c "from fastembed import TextEmbedding; TextEmbedding('sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2')"

COPY . .
COPY --from=frontend /static /app/static

# El índice se genera al arrancar si no existe (data/ es el disco persistente en Render)
EXPOSE 8000
CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}"]
