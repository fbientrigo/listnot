.PHONY: install lint test demo scan api dashboard clean

install:
	pip install -e ".[dev]"

lint:
	ruff check .

test:
	pytest -q

demo:
	PUCV_DEMO_MODE=true python scripts/demo_local.py

scan:
	python scripts/scan_for_forbidden_identifiers.py

api:
	uvicorn apps.api.main:app --reload

dashboard:
	streamlit run apps/dashboard/app.py

clean:
	rm -f data/*.db data/exports/*.csv data/reports/*.md data/reports/*.html
	find . -type d -name __pycache__ -prune -exec rm -rf {} +
