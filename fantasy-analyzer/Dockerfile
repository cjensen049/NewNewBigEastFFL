# Multi-stage build:
#   Stage 1 (node): builds the React frontend
#   Stage 2 (python): runs the FastAPI backend and serves the built React files
#
# Build context is the repo root (NNBE History/).
# Railway finds this file at fantasy-analyzer/Dockerfile and uses repo root as context.

# ---- Stage 1: build React frontend ----
FROM node:20-alpine AS frontend-build
WORKDIR /app/frontend
COPY fantasy-analyzer/frontend/package*.json ./
RUN npm ci
COPY fantasy-analyzer/frontend/ ./
RUN npm run build

# ---- Stage 2: Python backend ----
FROM python:3.11-slim AS backend
WORKDIR /app

# Install Python deps
COPY fantasy-analyzer/requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

# Copy backend source
COPY fantasy-analyzer/fantasy_analyzer/ ./fantasy_analyzer/
COPY fantasy-analyzer/backend/ ./backend/
COPY fantasy-analyzer/config.yaml ./
COPY fantasy-analyzer/pyproject.toml ./

# Copy the built React files from stage 1
COPY --from=frontend-build /app/frontend/dist ./frontend/dist

# Copy the league database (committed to git)
COPY fantasy-analyzer/data/league.db ./data/league.db

# Install the fantasy_analyzer package in the container
RUN pip install --no-cache-dir -e .

# Railway sets PORT env var; default to 8000 for local testing
ENV PORT=8000

# Use shell form via exec to get proper signal handling and PORT variable expansion
CMD ["sh", "-c", "exec uvicorn backend.main:app --host 0.0.0.0 --port ${PORT}"]
