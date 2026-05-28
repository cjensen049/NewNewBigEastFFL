# Multi-stage build:
#   Stage 1 (node): builds the React frontend
#   Stage 2 (python): runs the FastAPI backend and serves the built React files

# ---- Stage 1: build React frontend ----
FROM node:20-alpine AS frontend-build
WORKDIR /app/frontend
COPY frontend/package*.json ./
RUN NODE_OPTIONS=--use-system-ca npm ci
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

# Start FastAPI with uvicorn
CMD uvicorn backend.main:app --host 0.0.0.0 --port ${PORT}
