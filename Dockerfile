FROM python:3.12-slim

WORKDIR /app

RUN groupadd -r appuser && useradd -r -g appuser appuser

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY pass24_api_client/ pass24_api_client/
COPY bot/ bot/
COPY VERSION VERSION
COPY deploy/smoke_test.py deploy/smoke_test.py

RUN mkdir -p /app/data && chown -R appuser:appuser /app

USER appuser

ENV PYTHONUNBUFFERED=1

CMD ["python", "-m", "bot.main"]
