import os
import time
import requests
from datetime import datetime, timedelta
from deep_translator import GoogleTranslator

# === НАСТРОЙКИ ===
CHANNEL_USERNAME = "@rabota_v_serbii"  # username вашего канала
AREA_CODE = 113  # код Сербии на hh.ru
SEARCH_PERIOD_MINUTES = 30  # ищем вакансии за последние 30 минут
PER_PAGE = 100  # максимум вакансий на странице
SENT_IDS_FILE = "sent_ids.txt"  # файл для хранения отправленных ID

# Токен берём из переменной окружения (секрет GitHub)
BOT_TOKEN = os.environ.get("BOT_TOKEN")
if not BOT_TOKEN:
    raise ValueError("Не найден BOT_TOKEN. Добавьте секрет в настройках репозитория.")

def translate_text(text, target_lang="ru"):
    """Переводит текст на русский, если он не пустой."""
    if not text:
        return ""
    try:
        return GoogleTranslator(source="auto", target=target_lang).translate(text)
    except Exception as e:
        print(f"Ошибка перевода: {e}")
        return text  # возвращаем оригинал, если не удалось перевести

def get_sent_ids():
    """Читает список уже отправленных ID из файла."""
    try:
        with open(SENT_IDS_FILE, "r") as f:
            return set(line.strip() for line in f if line.strip())
    except FileNotFoundError:
        return set()

def save_sent_ids(ids):
    """Сохраняет обновлённый список ID в файл."""
    with open(SENT_IDS_FILE, "w") as f:
        for vac_id in ids:
            f.write(f"{vac_id}\n")

def fetch_new_vacancies():
    """Запрашивает свежие вакансии из hh.ru по Сербии."""
    date_from = (datetime.now() - timedelta(minutes=SEARCH_PERIOD_MINUTES)).isoformat(timespec="seconds")
    url = "https://api.hh.ru/vacancies"
    params = {
        "area": AREA_CODE,
        "date_from": date_from,
        "per_page": PER_PAGE,
        "page": 0,
        "order_by": "publication_time",
    }
    headers = {"User-Agent": "SerbiaJobsBot/1.0 (my@email.com)"}  # можно указать любой email
    response = requests.get(url, params=params, headers=headers)
    response.raise_for_status()
    return response.json().get("items", [])

def format_vacancy_message(vac):
    """Формирует текст поста для Telegram."""
    title = vac.get("name", "Без названия")
    company = vac.get("employer", {}).get("name", "Не указана")
    area = vac.get("area", {}).get("name", "Не указан")
    salary = vac.get("salary")
    if salary:
        salary_from = salary.get("from")
        salary_to = salary.get("to")
        currency = salary.get("currency", "")
        if salary_from and salary_to:
            salary_text = f"{salary_from}–{salary_to} {currency}"
        elif salary_from:
            salary_text = f"от {salary_from} {currency}"
        elif salary_to:
            salary_text = f"до {salary_to} {currency}"
        else:
            salary_text = "не указана"
    else:
        salary_text = "не указана"
    description = vac.get("snippet", {}).get("requirement") or vac.get("snippet", {}).get("responsibility") or ""
    # Переводим описание
    description_ru = translate_text(description)
    link = vac.get("alternate_url", "")

    message = (
        f"🇷🇸 *{title}*\n"
        f"🏢 Компания: {company}\n"
        f"📍 Город: {area}\n"
        f"💰 Зарплата: {salary_text}\n\n"
        f"📝 {description_ru}\n\n"
        f"🔗 [Открыть вакансию]({link})"
    )
    return message

def send_to_telegram(message):
    """Отправляет сообщение в канал через Telegram Bot API."""
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    data = {
        "chat_id": CHANNEL_USERNAME,
        "text": message,
        "parse_mode": "Markdown",
        "disable_web_page_preview": False,
    }
    response = requests.post(url, data=data)
    response.raise_for_status()
    return response.json()

def main():
    sent_ids = get_sent_ids()
    print(f"Уже отправлено ID: {len(sent_ids)}")

    vacancies = fetch_new_vacancies()
    print(f"Найдено вакансий за последние {SEARCH_PERIOD_MINUTES} мин: {len(vacancies)}")

    new_ids = []
    for vac in vacancies:
        vac_id = vac.get("id")
        if vac_id in sent_ids:
            continue
        try:
            message = format_vacancy_message(vac)
            send_to_telegram(message)
            print(f"Отправлена вакансия ID {vac_id}: {vac.get('name')}")
            new_ids.append(vac_id)
            time.sleep(2)  # пауза между отправками, чтобы не упереться в лимиты Telegram
        except Exception as e:
            print(f"Ошибка при обработке вакансии {vac_id}: {e}")

    if new_ids:
        sent_ids.update(new_ids)
        save_sent_ids(sent_ids)
        print(f"Добавлено и сохранено ID: {len(new_ids)}")
    else:
        print("Новых вакансий нет.")

if __name__ == "__main__":
    main()
