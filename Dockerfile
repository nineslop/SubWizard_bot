# Базовый образ Ubuntu
FROM ubuntu:22.04

# Обновление пакетов и установка Python
RUN apt update && apt upgrade -y && apt install python3-pip gcc python3-dev libpq-dev -y

# Устанавливаем зависимости
WORKDIR /app
COPY requirements.txt /app/
RUN pip3 install --no-cache-dir -r requirements.txt

# Копируем файлы приложения
COPY . /app

# Запускаем приложение
CMD ["sh", "-c", "alembic upgrade head && python3 SubWizard.py"]
