.PHONY: setup test lint typecheck api web ingest eval demo clean

setup:
	python -m pip install -e .
	cd frontend && npm install

test:
	python -m pytest backend/tests -v

lint:
	python -m ruff check backend

typecheck:
	python -m mypy backend/veridocs

api:
	python -m uvicorn veridocs.main:app --host 127.0.0.1 --port 8000 --reload

web:
	cd frontend && npm run dev

ingest:
	python scripts/ingest_filings.py --ticker AAPL --form 10-K

eval:
	python scripts/run_benchmark.py --config configs/evaluation.yaml

demo:
	python scripts/run_demo.py

clean:
	python -c "import shutil, os; [shutil.rmtree(p) for p in ['.pytest_cache', 'backend/__pycache__'] if os.path.exists(p)]"
