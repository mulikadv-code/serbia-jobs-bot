import os
import time
import requests
from datetime import datetime, timedelta
import feedparser
from deep_translator import GoogleTranslator

# === НАСТРОЙКИ ===
CHANNEL_USERNAME = "@rabota_v_serbii"  # username вашего канала
RSS_URL = "https://www.mojposao.net/rss"
SEARCH_PERIOD_MINUTES = 30
SENT_IDS_FILE = "sent_ids.txt"

BOT_TOKEN = os.environ.get("BOT_TOKEN")
if not BOT_TOKEN:
    raise ValueError("Не найден BOT_TOKEN. Добавьте секрет в настройках репозитория.")

def translate_text(text, target_lang="ru"):
    if not text:
        return ""
    try:
        return GoogleTranslator(source="auto", target=target_lang).translate(text)
    except Exception as e:
        print(f"Ошибка перевода: {e}")
        return text

def get_sent_ids():
    try:
        with open(SENT_IDS_FILE, "r") as f:
            return set(line.strip() for line in f if line.strip())
    except FileNotFoundError:
        return set()

def save_sent_ids(ids):
    with open(SENT_IDS_FILE, "w") as f:
        for vac_id in ids:
            f.write(f"{vac_id}\n")

def fetch_new_vacancies():
    """Парсит RSS-ленту MojPosao и возвращает новые вакансии за период."""
    feed = feedparser.parse(RSS_URL)
    entries = feed.entries
    print(f"Всего записей в RSS: {len(entries)}")

    new_entries = []
    cutoff = datetime.now() - timedelta(minutes=SEARCH_PERIOD_MINUTES)
    for entry in entries:
        # Пытаемся получить дату публикации
        pub_date = None
        if hasattr(entry, 'published_parsed') and entry.published_parsed:
            pub_date = datetime(*entry.published_parsed[:6])
        elif hasattr(entry, 'updated_parsed') and entry.updated_parsed:
            pub_date = datetime(*entry.updated_parsed[:6])
        else:
            # Если даты нет, считаем вакансию новой (на всякий случай)
            new_entries.append(entry)
            continue

        if pub_date >= cutoff:
            new_entries.append(entry)

    print(f"Новых вакансий за {SEARCH_PERIOD_MINUTES} мин: {len(new_entries)}")
    return new_entries

def format_vacancy_message(entry):
    """Формирует пост из записи RSS."""
    title = entry.get('title', 'Без названия')
    link = entry.get('link', '')
    # Пытаемся извлечь описание из summary или description
    description = ''
    if 'summary' in entry:
        description = entry.summary
    elif 'description' in entry:
        description = entry.description
    # Убираем HTML-теги (простая очистка)
    import re
    description_clean = re.sub('<[^<]+?>', '', description)
    # Переводим описание
    description_ru = translate_text(description_clean)

    message = (
        f"🇷🇸 *{title}*\n\n"
        f"📝 {description_ru}\n\n"
        f"🔗 [Открыть вакансию]({link})"
    )
    return message

def send_to_telegram(message):
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

    entries = fetch_new_vacancies()

    new_ids = []
    for entry in entries:
        # Используем ссылку как уникальный идентификатор
        vac_id = entry.get('link') or entry.get('id') or entry.get('title')
        if vac_id in sent_ids:
            continue
        try:
            message = format_vacancy_message(entry)
            send_to_telegram(message)
            print(f"Отправлена вакансия: {entry.get('title', '')}")
            new_ids.append(vac_id)
            time.sleep(2)
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
