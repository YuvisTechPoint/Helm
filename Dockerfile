FROM python:3.12-slim

RUN apt-get update && apt-get install -y --no-install-recommends ffmpeg && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY pyproject.toml alembic.ini run_api.py run_worker.py run_e2e.py ./
COPY packages ./packages
COPY apps ./apps
COPY alembic ./alembic
COPY tests ./tests

RUN pip install --no-cache-dir -e .

ENV PYTHONPATH=packages/core:apps/youtube:apps/acquisition:apps/api

CMD ["python", "run_api.py"]
