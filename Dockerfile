# Artificial Education — Cloud Run container
FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PORT=8080

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# SQLite DB lives at /app by default; mount a volume for persistence if needed.
EXPOSE 8080

CMD exec gunicorn app:app --bind 0.0.0.0:$PORT --workers 2 --timeout 120
