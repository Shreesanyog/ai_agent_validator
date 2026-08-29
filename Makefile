# AVaaS developer shortcuts. Backend commands assume backend/.venv is active
# or that you run them inside the backend/ directory.

.PHONY: help install backend frontend mock test migrate compose-up compose-down

help:
	@echo "install       Install backend + frontend deps"
	@echo "backend       Run the FastAPI backend (port 8000)"
	@echo "frontend      Run the React dev server (port 5173)"
	@echo "mock          Run the standalone mock agent (port 9100)"
	@echo "migrate       Apply Alembic migrations (alembic upgrade head)"
	@echo "test          Run the backend test suite"
	@echo "compose-up    Build and start the full Docker stack"
	@echo "compose-down  Stop the Docker stack"

install:
	cd backend && pip install -r requirements.txt
	cd frontend && npm install

backend:
	cd backend && uvicorn app.main:app --reload --port 8000

frontend:
	cd frontend && npm run dev

mock:
	cd mock-agent && uvicorn main:app --port 9100

migrate:
	cd backend && alembic upgrade head

test:
	cd backend && pytest -q

compose-up:
	docker compose up --build

compose-down:
	docker compose down
