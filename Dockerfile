FROM python:3.12-slim

RUN apt-get update && apt-get install -y --no-install-recommends ffmpeg && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY pyproject.toml alembic.ini README.md ./
COPY src ./src
COPY scripts ./scripts
COPY alembic ./alembic
COPY run_api.py run_worker.py run_e2e.py ./

RUN pip install --no-cache-dir -e .

ENV PYTHONPATH=src

CMD ["python", "run_api.py"]
