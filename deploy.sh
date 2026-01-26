#!/bin/bash

# Остановка скрипта при ошибке
set -e

# Определение цветов для вывода
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

# Определение директории проекта (где лежит скрипт)
PROJECT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
USER_NAME="$(whoami)"
SERVICE_NAME="tlg_keywords_follower"
VENV_DIR="$PROJECT_DIR/.venv"
PYTHON_BIN="$VENV_DIR/bin/python"
PIP_BIN="$VENV_DIR/bin/pip"

echo -e "${GREEN}🚀 Начинаю развертывание tlg_keywords_follower...${NC}"
echo "📁 Директория проекта: $PROJECT_DIR"
echo "👤 Пользователь: $USER_NAME"

# 1. Обновление кода из репозитория (если есть .git)
if [ -d "$PROJECT_DIR/.git" ]; then
    echo -e "\n${YELLOW}📥 Обновление кода из git...${NC}"
    git pull
else
    echo -e "\n${YELLOW}⚠️ Git репозиторий не найден, пропускаю git pull${NC}"
fi

# 2. Настройка виртуального окружения
echo -e "\n${YELLOW}🐍 Проверка Python окружения...${NC}"
if [ ! -f "$PIP_BIN" ]; then
    echo "Virtual environment not found or broken (pip missing). Creating..."
    rm -rf "$VENV_DIR"
    python3 -m venv "$VENV_DIR"
fi

# 3. Установка зависимостей
echo -e "\n${YELLOW}📦 Установка зависимостей...${NC}"
"$PIP_BIN" install --upgrade pip
"$PIP_BIN" install -r "$PROJECT_DIR/requirements.txt"

# 4. Проверка конфига .env
echo -e "\n${YELLOW}⚙️ Проверка конфигурации...${NC}"
if [ ! -f "$PROJECT_DIR/.env" ]; then
    echo -e "${RED}❌ Файл .env не найден!${NC}"
    if [ -f "$PROJECT_DIR/.env.example" ]; then
        echo "Копирую .env.example в .env..."
        cp "$PROJECT_DIR/.env.example" "$PROJECT_DIR/.env"
        echo -e "${RED}⚠️ ПОЖАЛУЙСТА, ОТРЕДАКТИРУЙТЕ .env ПЕРЕД ЗАПУСКОМ!${NC}"
        echo -e "${RED}Скрипт продолжит создание сервиса, но бот не запустится без валидных токенов.${NC}"
    fi
else
    echo "✅ Файл .env найден"
fi

if [ ! -d "$PROJECT_DIR/app_data" ]; then
    mkdir -p "$PROJECT_DIR/app_data"
fi

if [ ! -f "$PROJECT_DIR/app_data/config.json" ]; then
    echo "Копирование config.example.json в app_data/config.json..."
    cp "$PROJECT_DIR/app_data/config.example.json" "$PROJECT_DIR/app_data/config.json"
fi


# 5. Создание и регистрация systemd сервиса
echo -e "\n${YELLOW}🔧 Настройка systemd сервиса...${NC}"

SERVICE_FILE_CONTENT="[Unit]
Description=Telegram UserBot Service
After=network.target

[Service]
Type=simple
User=$USER_NAME
WorkingDirectory=$PROJECT_DIR
ExecStart=$PYTHON_BIN -m app.main
Restart=always
RestartSec=10
EnvironmentFile=$PROJECT_DIR/.env
StandardOutput=syslog
StandardError=syslog
SyslogIdentifier=$SERVICE_NAME

[Install]
WantedBy=multi-user.target"

echo "Генерация файла сервиса..."
echo "$SERVICE_FILE_CONTENT" | sudo tee "/etc/systemd/system/$SERVICE_NAME.service" > /dev/null

echo "Перезагрузка демона systemd..."
sudo systemctl daemon-reload

echo "Включение автозагрузки и запуск сервиса..."
sudo systemctl enable "$SERVICE_NAME"
sudo systemctl restart "$SERVICE_NAME"

# 6. Проверка статуса
echo -e "\n${YELLOW}📊 Статус сервиса:${NC}"
systemctl status "$SERVICE_NAME" --no-pager

echo -e "\n${GREEN}✅ Развертывание завершено!${NC}"
echo "Для просмотра логов используйте: journalctl -u $SERVICE_NAME -f"
