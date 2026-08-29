FROM python:3.12-slim

# System deps for Playwright chromium are heavy; the browser adapter is optional,
# so the base image stays slim. Install Playwright browsers at runtime only if
# BROWSER validation is needed (see README).
WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 8000
# Apply migrations then start. In dev AUTO_CREATE_TABLES can handle schema instead.
CMD ["sh", "-c", "alembic upgrade head || true; uvicorn app.main:app --host 0.0.0.0 --port 8000"]
