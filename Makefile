.PHONY: install test api worker e2e dev dev-lite docker-up docker-down clean

install:
	pip install -e ".[dev]"

test:
	pytest -q

api:
	python run_api.py

worker:
	python run_worker.py

e2e:
	python run_e2e.py

e2e-full: test e2e

dev:
	python scripts/dev.py

dev-lite:
	START_WORKER=0 python scripts/dev.py

docker-up:
	docker compose up --build

docker-down:
	docker compose down

clean:
	rm -rf .pytest_cache **/__pycache__ *.egg-info src/*.egg-info
	find . -name "*.pyc" -delete 2>/dev/null || true
