# Multi-stage build:
#   Stage 1 (node): builds the React frontend
#   Stage 2 (python): runs the FastAPI backend and serves the built React files
#
# Build context is fantasy-analyzer/ (set by railway.json watchPatterns / root).
# Railway finds this file at fantasy-analyzer/Dockerfile.

# ---- Stage 1: build React frontend ----
FROM node:20-alpine AS frontend-build
WORKDIR /app/frontend
COPY frontend/package*.json ./
RUN npm ci
COPY frontend/ ./
RUN npm run build

# ---- Stage 2: Python backend ----
FROM python:3.11-slim AS backend
WORKDIR /app

# Install Python deps
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

# Copy backend source
COPY fantasy_analyzer/ ./fantasy_analyzer/
COPY backend/ ./backend/
COPY config.yaml ./
COPY pyproject.toml ./

# Copy the built React files from stage 1
COPY --from=frontend-build /app/frontend/dist ./frontend/dist

# Copy the league database (committed to git)
COPY data/league.db ./data/league.db

# Install the fantasy_analyzer package in the container
RUN pip install --no-cache-dir -e .

# Railway sets PORT env var; default to 8000 for local testing
ENV PORT=8000

# Use shell form via exec to get proper signal handling and PORT variable expansion
CMD ["sh", "-c", "exec uvicorn backend.main:app --host 0.0.0.0 --port ${PORT}"]
