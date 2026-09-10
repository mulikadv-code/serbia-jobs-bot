import os
import time
import requests
import re
from datetime import datetime
import feedparser
from deep_translator import GoogleTranslator

# === НАСТРОЙКИ ===
CHANNEL_USERNAME = "@rabita_v_serbii"
RSS_URL = "https://www.helloworld.rs/rss"
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


def fetch_vacancies():
    """Скачивает RSS и возвращает все записи."""
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                      "AppleWebKit/537.36 (KHTML, like Gecko) "
                      "Chrome/120.0.0.0 Safari/537.36",
        "Accept": "application/rss+xml, application/xml, text/xml, */*",
    }
    try:
        response = requests.get(RSS_URL, headers=headers, timeout=30)
        response.raise_for_status()
        feed = feedparser.parse(response.content)
        entries = feed.entries
        print(f"Всего записей в RSS: {len(entries)}")
        return entries
    except Exception as e:
        print(f"Ошибка при загрузке RSS: {e}")
        return []


def clean_html(text):
    """Убирает HTML-теги из строки."""
    if not text:
        return ""
    return re.sub(r"<[^<]+?>", "", text).strip()


def format_vacancy_message(entry):
    """Формирует сообщение для Telegram."""
    title = entry.get("title", "Без названия")
    link = entry.get("link", "")

    # Описание: пробуем разные поля
    description = ""
    for field in ("summary", "description"):
        if field in entry and entry[field]:
            description = entry[field]
            break
    description_clean = clean_html(description)

    # Ограничиваем длину описания, чтобы Telegram не ругался
    if len(description_clean) > 700:
        description_clean = description_clean[:700] + "..."

    description_ru = translate_text(description_clean) if description_clean else ""
    title_ru = translate_text(title)

    message = (
        f"🇷🇸 *{title_ru}*\n\n"
        f"📝 {description_ru}\n\n"
        f"🔗 [Открыть вакансию]({link})"
    )
    # Telegram ограничивает длину сообщения 4096 символами
    if len(message) > 4000:
        message = message[:3990] + "..."
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

    entries = fetch_vacancies()

    new_ids = []
    for entry in entries:
        vac_id = entry.get("link") or entry.get("id") or entry.get("title")
        if not vac_id:
            continue
        if vac_id in sent_ids:
            continue
        try:
            message = format_vacancy_message(entry)
            send_to_telegram(message)
            print(f"✅ Отправлено: {entry.get('title', '')[:60]}")
            new_ids.append(vac_id)
            time.sleep(2)
        except Exception as e:
            print(f"❌ Ошибка при отправке '{entry.get('title', '')[:40]}': {e}")

    if new_ids:
        sent_ids.update(new_ids)
        save_sent_ids(sent_ids)
        print(f"Сохранено новых ID: {len(new_ids)}")
    else:
        print("Новых вакансий нет.")


if __name__ == "__main__":
    main()
