.PHONY: env install run dev test clean help

# Python virtual environment
VENV = .venv
PYTHON = $(VENV)/bin/python
PIP = $(VENV)/bin/pip
UVICORN = $(VENV)/bin/uvicorn

help:
	@echo "Gmail Agent - Makefile Commands"
	@echo "================================"
	@echo "make env       - Create virtual environment"
	@echo "make install   - Install dependencies"
	@echo "make run       - Run the FastAPI server"
	@echo "make dev       - Run server with auto-reload"
	@echo "make test      - Run tests (if available)"
	@echo "make clean     - Remove virtual environment and cache"

env:
	python3 -m venv $(VENV)
	@echo "Virtual environment created. Activate with: source $(VENV)/bin/activate"

install: env
	$(PIP) install --upgrade pip
	$(PIP) install -r requirements.txt
	@echo "Dependencies installed successfully"

run:
	$(UVICORN) server.api:app --host 0.0.0.0 --port 8000

dev:
	$(UVICORN) server.api:app --host 0.0.0.0 --port 8000 --reload

test:
	@echo "No tests configured yet"

clean:
	rm -rf $(VENV)
	find . -type d -name "__pycache__" -exec rm -rf {} +
	find . -type f -name "*.pyc" -delete
	@echo "Cleaned up virtual environment and cache files"
