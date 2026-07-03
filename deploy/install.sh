#!/bin/bash
# Интерактивная установка PASS24 Telegram Bot (Docker).
# Запуск: bash deploy/install.sh
# Или из корня репозитория на сервере после git clone.
set -eu

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
INSTALL_DIR="${INSTALL_DIR:-/opt/pass24-telegram-bot}"
ENV_FILE="$PROJECT_ROOT/.env"

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
NC='\033[0m'

info()  { echo -e "${CYAN}==>${NC} $*"; }
ok()    { echo -e "${GREEN}OK${NC} $*"; }
warn()  { echo -e "${YELLOW}WARN${NC} $*"; }
fail()  { echo -e "${RED}ERROR${NC} $*" >&2; exit 1; }

need_root() {
  if [ "$(id -u)" -ne 0 ]; then
    fail "Запустите от root: sudo bash deploy/install.sh"
  fi
}

ensure_project_root() {
  if [ -f "$PROJECT_ROOT/docker-compose.yml" ]; then
    cd "$PROJECT_ROOT"
    return
  fi

  if [ -f "$INSTALL_DIR/docker-compose.yml" ]; then
    PROJECT_ROOT="$INSTALL_DIR"
    ENV_FILE="$PROJECT_ROOT/.env"
    cd "$PROJECT_ROOT"
    return
  fi

  info "Репозиторий не найден в $INSTALL_DIR"
  echo ""
  echo "Сначала клонируйте проект, например:"
  echo "  git clone https://github.com/icebeerg182/pass24-telegram-bot.git $INSTALL_DIR"
  echo "  cd $INSTALL_DIR && bash deploy/install.sh"
  exit 1
}

stop_legacy_bot() {
  systemctl stop pass24-telegram-bot.service 2>/dev/null || true
  systemctl disable pass24-telegram-bot.service 2>/dev/null || true
  rm -f /etc/systemd/system/pass24-telegram-bot.service
  systemctl daemon-reload 2>/dev/null || true
}

ensure_docker() {
  if command -v docker >/dev/null 2>&1 && docker compose version >/dev/null 2>&1; then
    ok "Docker $(docker --version | awk '{print $3}' | tr -d ',')"
    ok "Compose $(docker compose version --short 2>/dev/null || docker compose version)"
    return
  fi

  info "Устанавливаю Docker..."
  export DEBIAN_FRONTEND=noninteractive
  apt-get update -qq
  apt-get install -y -qq docker.io docker-compose-v2 curl ca-certificates
  systemctl enable --now docker
  ok "Docker установлен"
}

ensure_python_tools() {
  if ! command -v python3 >/dev/null 2>&1; then
    info "Устанавливаю python3..."
    apt-get install -y -qq python3 python3-pip
  fi

  local missing=0
  python3 -c "import requests" 2>/dev/null || missing=1
  python3 -c "import dotenv" 2>/dev/null || missing=1
  python3 -c "import pytz" 2>/dev/null || missing=1

  if [ "$missing" -eq 1 ]; then
    info "Устанавливаю Python-зависимости для проверки..."
    apt-get install -y -qq python3-requests python3-pip 2>/dev/null || true
    python3 -m pip install -q --break-system-packages requests python-dotenv pytz 2>/dev/null \
      || python3 -m pip install -q requests python-dotenv pytz 2>/dev/null \
      || apt-get install -y -qq python3-dotenv python3-tz
  fi

  if ! python3 -c "import requests, dotenv, pytz" 2>/dev/null; then
    fail "Не удалось установить python3-модули: requests, python-dotenv, pytz"
  fi
  ok "Python-зависимости для проверки готовы"
}

normalize_phone() {
  local p="$1"
  p="${p// /}"
  p="${p//-/}"
  if [[ "$p" =~ ^8[0-9]{10}$ ]]; then
    echo "+7${p:1}"
  elif [[ "$p" =~ ^7[0-9]{10}$ ]]; then
    echo "+$p"
  else
    echo "$p"
  fi
}

prompt_nonempty() {
  local label="$1"
  local var_name="$2"
  local secret="${3:-0}"
  local value=""
  while [ -z "$value" ]; do
    if [ "$secret" = "1" ]; then
      read -rsp "$label: " value
      echo ""
    else
      read -rp "$label: " value
    fi
    value="$(echo "$value" | sed 's/^[[:space:]]*//;s/[[:space:]]*$//')"
    if [ -z "$value" ]; then
      warn "Поле обязательно."
    fi
  done
  printf -v "$var_name" '%s' "$value"
}

validate_telegram_token() {
  TELEGRAM_BOT_TOKEN="$1" python3 -c "
import os, sys
sys.path.insert(0, '$PROJECT_ROOT')
from deploy.validate_env import validate_telegram
ok, msg = validate_telegram(os.environ['TELEGRAM_BOT_TOKEN'])
print(msg)
sys.exit(0 if ok else 1)
"
}

validate_pass24_creds() {
  PASS24_PHONE="$1" PASS24_PASSWORD="$2" PASS24_ADDRESS_KEYWORD="$3" \
    python3 -c "
import os, sys
sys.path.insert(0, '$PROJECT_ROOT')
from deploy.validate_env import validate_pass24
ok, msg = validate_pass24(
    os.environ['PASS24_PHONE'],
    os.environ['PASS24_PASSWORD'],
    os.environ.get('PASS24_ADDRESS_KEYWORD', ''),
)
print(msg)
sys.exit(0 if ok else 1)
"
}

list_addresses() {
  PASS24_PHONE="$1" PASS24_PASSWORD="$2" \
    python3 -c "
import os, sys
sys.path.insert(0, '$PROJECT_ROOT')
from deploy.validate_env import list_pass24_addresses
for name in list_pass24_addresses(os.environ['PASS24_PHONE'], os.environ['PASS24_PASSWORD']):
    print(name)
"
}

prompt_telegram() {
  echo ""
  info "Telegram-бот"
  while true; do
    prompt_nonempty "TELEGRAM_BOT_TOKEN (от @BotFather)" TELEGRAM_BOT_TOKEN
    if validate_telegram_token "$TELEGRAM_BOT_TOKEN"; then
      ok "Токен Telegram принят"
      break
    fi
    warn "Токен не прошёл проверку. Попробуйте снова."
  done

  while true; do
    prompt_nonempty "TELEGRAM_ADMIN_USER_IDS (через запятую)" TELEGRAM_ADMIN_USER_IDS
    if echo "$TELEGRAM_ADMIN_USER_IDS" | grep -Eq '^[0-9]+(,[[:space:]]*[0-9]+)*$'; then
      break
    fi
    warn "Укажите числовые ID через запятую, например: 123456789,987654321"
  done

  read -rp "TELEGRAM_ALLOWED_USER_IDS (необязательно, Enter — пропустить): " TELEGRAM_ALLOWED_USER_IDS
  TELEGRAM_ALLOWED_USER_IDS="$(echo "$TELEGRAM_ALLOWED_USER_IDS" | sed 's/^[[:space:]]*//;s/[[:space:]]*$//')"
}

prompt_pass24() {
  echo ""
  info "PASS24 (как в приложении жителя)"
  while true; do
    prompt_nonempty "PASS24_PHONE (+79...)" PASS24_PHONE
    PASS24_PHONE="$(normalize_phone "$PASS24_PHONE")"
    prompt_nonempty "PASS24_PASSWORD" PASS24_PASSWORD 1

    echo ""
    info "Проверяю логин PASS24..."
    set +e
    addresses="$(list_addresses "$PASS24_PHONE" "$PASS24_PASSWORD" 2>&1)"
    rc=$?
    set -e
    if [ "$rc" -ne 0 ]; then
      warn "$addresses"
      warn "Логин/пароль не приняты. Повторите ввод."
      continue
    fi
    ok "Логин PASS24 успешен"

    if [ -n "$addresses" ]; then
      echo ""
      echo "Доступные адреса:"
      echo "$addresses" | nl -w2 -s'. '
      echo ""
      if [ "$(echo "$addresses" | wc -l)" -gt 1 ]; then
        read -rp "PASS24_ADDRESS_KEYWORD (подстрока названия, Enter — первый адрес): " PASS24_ADDRESS_KEYWORD
      else
        PASS24_ADDRESS_KEYWORD=""
        ok "Один адрес — фильтр не нужен"
      fi
    else
      PASS24_ADDRESS_KEYWORD=""
    fi

    set +e
    out="$(validate_pass24_creds "$PASS24_PHONE" "$PASS24_PASSWORD" "$PASS24_ADDRESS_KEYWORD" 2>&1)"
    rc=$?
    set -e
    if [ "$rc" -eq 0 ]; then
      ok "$out"
      break
    fi
    warn "$out"
    warn "Проверьте PASS24_ADDRESS_KEYWORD или учётные данные."
  done

  PASS24_PASS_HOURS="${PASS24_PASS_HOURS:-24}"
  PASS24_VEHICLE_TYPE_KEYWORD="${PASS24_VEHICLE_TYPE_KEYWORD:-легков}"
  read -rp "PASS24_PASS_HOURS [$PASS24_PASS_HOURS]: " _hours
  if [ -n "$_hours" ]; then PASS24_PASS_HOURS="$_hours"; fi

  if [ -n "$addresses" ]; then
    ADDRESS_COUNT="$(echo "$addresses" | wc -l | tr -d ' ')"
  else
    ADDRESS_COUNT=0
  fi
}

prompt_yes_no() {
  local label="$1"
  local var_name="$2"
  local default="${3:-n}"
  local hint="y/N"
  [ "$default" = "y" ] && hint="Y/n"
  read -rp "$label [$hint]: " ans
  ans="${ans:-$default}"
  if [[ "$ans" =~ ^[YyДд]$ ]]; then
    printf -v "$var_name" '%s' 'true'
  else
    printf -v "$var_name" '%s' 'false'
  fi
}

prompt_bot_settings() {
  echo ""
  info "Настройки поведения бота"

  prompt_yes_no "Спрашивать тип ТС (легковой/грузовой) при заказе?" BOT_ASK_VEHICLE_TYPE n
  if [ "$BOT_ASK_VEHICLE_TYPE" != "true" ]; then
    read -rp "Тип ТС по умолчанию [легков/грузовой] ($PASS24_VEHICLE_TYPE_KEYWORD): " _vt
    if [ -n "$_vt" ]; then PASS24_VEHICLE_TYPE_KEYWORD="$_vt"; fi
  fi

  prompt_yes_no "Спрашивать подтверждение перед созданием пропуска?" BOT_CONFIRM_BEFORE_CREATE y

  if [ "${ADDRESS_COUNT:-0}" -gt 1 ]; then
    prompt_yes_no "Добавить кнопку выбора адреса по умолчанию?" BOT_ENABLE_ADDRESS_PICKER y
  else
    BOT_ENABLE_ADDRESS_PICKER=false
    ok "Один адрес — кнопка выбора адреса не нужна"
  fi
}

write_env() {
  if [ -f "$ENV_FILE" ]; then
    cp "$ENV_FILE" "${ENV_FILE}.bak.$(date +%Y%m%d%H%M%S)"
    ok "Старый .env сохранён как backup"
  fi

  cat >"$ENV_FILE" <<EOF
TELEGRAM_BOT_TOKEN=$TELEGRAM_BOT_TOKEN
TELEGRAM_ALLOWED_USER_IDS=$TELEGRAM_ALLOWED_USER_IDS
TELEGRAM_ADMIN_USER_IDS=$TELEGRAM_ADMIN_USER_IDS

PASS24_PHONE=$PASS24_PHONE
PASS24_PASSWORD=$PASS24_PASSWORD
PASS24_ADDRESS_KEYWORD=$PASS24_ADDRESS_KEYWORD
PASS24_PASS_HOURS=$PASS24_PASS_HOURS
PASS24_VEHICLE_TYPE_KEYWORD=$PASS24_VEHICLE_TYPE_KEYWORD
PASS24_VEHICLE_TYPE_ID=

BOT_ASK_VEHICLE_TYPE=$BOT_ASK_VEHICLE_TYPE
BOT_CONFIRM_BEFORE_CREATE=$BOT_CONFIRM_BEFORE_CREATE
BOT_ENABLE_ADDRESS_PICKER=$BOT_ENABLE_ADDRESS_PICKER
EOF
  chmod 600 "$ENV_FILE"
  ok ".env создан"
}

final_validate() {
  info "Финальная проверка .env..."
  if python3 "$SCRIPT_DIR/validate_env.py" --env "$ENV_FILE"; then
    ok "Все учётные данные валидны"
  else
    fail "Проверка .env не прошла"
  fi
}

start_bot() {
  mkdir -p "$PROJECT_ROOT/data"
  chmod 755 "$PROJECT_ROOT/data"

  info "Сборка и запуск Docker..."
  cd "$PROJECT_ROOT"
  docker compose build
  docker compose up -d
  docker compose ps

  info "Smoke-test в контейнере..."
  sleep 3
  if docker compose exec -T pass24-telegram-bot python deploy/smoke_test.py; then
    ok "Бот запущен и PASS24 доступен"
  else
    warn "Контейнер запущен, но smoke-test не прошёл — см. docker compose logs"
  fi
}

print_done() {
  echo ""
  echo -e "${GREEN}=== Установка завершена ===${NC}"
  echo "Каталог: $PROJECT_ROOT"
  echo "Логи:    docker compose logs -f"
  echo "Статус:  docker compose ps"
  echo ""
  echo "Проверка в Telegram: /start → BMW А121МР77"
}

main() {
  echo ""
  echo -e "${CYAN}PASS24 Telegram Bot — интерактивная установка${NC}"
  echo ""

  need_root
  ensure_project_root
  stop_legacy_bot
  ensure_docker
  ensure_python_tools

  if [ -f "$ENV_FILE" ]; then
    echo ""
    read -rp "Найден существующий .env. Пересоздать? [y/N]: " reconfigure
    if [[ ! "$reconfigure" =~ ^[Yy]$ ]]; then
      info "Использую существующий .env"
      final_validate
      start_bot
      print_done
      exit 0
    fi
  fi

  prompt_telegram
  prompt_pass24
  prompt_bot_settings
  write_env
  final_validate
  start_bot
  print_done
}

main "$@"
