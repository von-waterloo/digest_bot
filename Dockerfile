# Dockerfile для Flask сервера
FROM python:3.10-slim

# Устанавливаем рабочую директорию
WORKDIR /app

# Копируем все файлы в контейнер
COPY . /app

# Устанавливаем зависимости
RUN pip install --no-cache-dir -r requirements.txt

# Запускаем сервер на порту 5000
EXPOSE 5000
CMD ["python", "server.py"]
