# Dockerfile для Flask сервера
FROM python:3.10-slim

# Устанавливаем рабочую директорию
WORKDIR /app

# Копируем все файлы в контейнер
COPY . /app

# Устанавливаем зависимости
RUN pip install --no-cache-dir -r requirements.txt

# Запускаем сервер с помощью Gunicorn на порту 5000 и запускаем news_checker.py
EXPOSE 5000
CMD ["sh", "-c", "gunicorn --bind 0.0.0.0:5000 server:app & python3 news_checker.py"]
