# Build from the repository root:  docker compose build
FROM python:3.12-slim

WORKDIR /srv
# Editable install keeps the code under /srv/backend, so the app's "project root" (/srv) holds storage/ and evals/.
COPY backend/pyproject.toml backend/pyproject.toml
COPY backend/app backend/app
RUN pip install --no-cache-dir -e ./backend
COPY evals evals
RUN mkdir -p storage/uploads storage/vectorstore

EXPOSE 8000
CMD ["uvicorn", "app.main:create_app", "--factory", "--host", "0.0.0.0", "--port", "8000", "--app-dir", "/srv/backend"]
