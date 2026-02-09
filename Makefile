.PHONY: setup start test clean demo

setup:
	@./scripts/setup_uv.sh

start:
	@uv run uvicorn src.pincer.server:app --host 0.0.0.0 --port 8080 --workers 4

test:
	@uv run pytest

clean:
	@rm -rf .venv
	@find . -type d -name "__pycache__" -exec rm -rf {} +

demo:
	@uv run python src/agent/demo.py
