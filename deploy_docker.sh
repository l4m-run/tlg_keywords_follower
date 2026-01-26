#!/bin/bash
set -e

GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

echo -e "${GREEN}🐳 Запуск tlg_keywords_follower в Docker...${NC}"

# Проверка Docker
if ! command -v docker &> /dev/null; then
    echo -e "${RED}❌ Docker не найден! Пожалуйста, установите Docker.${NC}"
    exit 1
fi

# Определение команды docker-compose
if command -v docker-compose &> /dev/null; then
    DOCKER_COMPOSE_CMD="docker-compose"
elif docker compose version &> /dev/null; then
    DOCKER_COMPOSE_CMD="docker compose"
else
    echo -e "${RED}❌ docker-compose не найден! (ни как отдельная утилита, ни как плагин 'docker compose')${NC}"
    exit 1
fi
echo "Использую: $DOCKER_COMPOSE_CMD"

# Проверка файлов конфигурации
if [ ! -d "app_data" ]; then
    mkdir -p app_data
fi

if [ ! -f .env ]; then
    echo -e "${RED}❌ Файл .env не найден! Скопируйте .env.example и настройте его.${NC}"
    exit 1
fi

if [ ! -f app_data/config.json ]; then
    echo -e "${YELLOW}⚠️ app_data/config.json не найден, создаю из примера.${NC}"
    cp app_data/config.example.json app_data/config.json
fi


# Проверка файла сессии для корректного монтирования
if [ ! -f app_data/userbot_session.session ]; then
    echo -e "${YELLOW}⚠️ Файл сессии не найден. Первый запуск требует авторизации.${NC}"
    echo -e "${YELLOW}Сейчас будет запущен интерактивный контейнер для входа.${NC}"
    echo -e "Введите номер телефона и код подтверждения, когда потребуется."
    
    # Создаем пустой файл, чтобы docker-compose не создал директорию (хотя мы монтируем папку, но на всякий случай)
    touch app_data/userbot_session.session
    
    # Запускаем интерактивно
    $DOCKER_COMPOSE_CMD run --rm bot
    
    echo -e "${GREEN}✅ Авторизация пройдена (надеюсь). Запускаю сервис в фоне.${NC}"
fi

# Сборка и запуск
echo -e "\n${YELLOW}🏗 Сборка и запуск контейнеров...${NC}"
$DOCKER_COMPOSE_CMD up -d --build

echo -e "\n${GREEN}✅ Сервис запущен!${NC}"
echo "Логи: $DOCKER_COMPOSE_CMD logs -f"
