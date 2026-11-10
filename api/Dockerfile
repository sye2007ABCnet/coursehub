# Образ серверной части (API)
FROM python:3.12-slim

WORKDIR /app

# Сначала устанавливаются зависимости: этот слой кэшируется
# и пересобирается только при изменении requirements.txt
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY main.py .

# Приложение запускается от обычного пользователя, а не от root
RUN useradd --create-home app
USER app

EXPOSE 8000
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
