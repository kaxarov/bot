import requests
from bs4 import BeautifulSoup
import telebot
import time
import json
from datetime import datetime
from telebot.apihelper import ApiTelegramException

# 🔹 Telegram bot token and channel ID
TELEGRAM_BOT_TOKEN = '7616049706:AAHVDFkoGsoVrs7Ad4GhFx0t46lzqZEeOUc'  # Replace with your bot token
TELEGRAM_CHANNEL_ID = '-1002377763042'  # Replace with your Telegram channel ID
ADMIN_ID = "736757552"  # Your Telegram user ID to receive status updates

# 🔹 Website credentials & API URLs
LOGIN_API_URL = "https://logistics-edi.azurewebsites.net/login"
DASHBOARD_URL = "https://logistics-edi.azurewebsites.net/"
EMAIL = "rrood@mercer-trans.com"
PASSWORD = "Dispatch24!"

bot = telebot.TeleBot(TELEGRAM_BOT_TOKEN)

LOAD_IDS_FILE = 'sent_load_ids.json'

def login_and_get_session():
    session = requests.Session()
    response = session.get("https://logistics-edi.azurewebsites.net/login")
    html = response.text
    soup = BeautifulSoup(html, "html.parser")
    element = soup.find('meta', {'name': 'csrf_token'})
    csrf_token = element.get('content')
    cookie = response.cookies
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:136.0) Gecko/20100101 Firefox/136.0',
        'Accept': '*/*',
        'Accept-Language': 'en-US,en;q=0.5',
        'Accept-Encoding': 'gzip, deflate, br, zstd',
        'Content-Type': 'multipart/form-data; boundary=----geckoformboundarybot',
        'Origin': 'https://logistics-edi.azurewebsites.net',
        'Connection': 'keep-alive',
        'Referer': 'https://logistics-edi.azurewebsites.net/login.php',
        'Sec-Fetch-Dest': 'empty',
        'Sec-Fetch-Mode': 'cors',
        'Sec-Fetch-Site': 'same-origin',
        'Priority': 'u=0',
    }

    payload = '\n------geckoformboundarybot\nContent-Disposition: form-data; name="email"\n\nrrood@mercer-trans.com' \
    '\n------geckoformboundarybot\nContent-Disposition: form-data; name="password"\n\nDispatch24!' \
    f'\n------geckoformboundarybot\nContent-Disposition: form-data; name="csrf_token"\n\n{csrf_token}\n------geckoformboundarybot--'
    response = session.post('https://logistics-edi.azurewebsites.net/php/login.php', cookies=cookie, headers=headers, data=payload)
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:136.0) Gecko/20100101 Firefox/136.0',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
        'Accept-Language': 'en-US,en;q=0.5',
        'Accept-Encoding': 'gzip, deflate, br, zstd',
        'Connection': 'keep-alive',
        'Referer': 'https://logistics-edi.azurewebsites.net/',
        'Upgrade-Insecure-Requests': '1',
        'Sec-Fetch-Dest': 'document',
        'Sec-Fetch-Mode': 'navigate',
        'Sec-Fetch-Site': 'same-origin',
        'Priority': 'u=0, i',
        'Cache-Control': 'max-age=0',
    }
    return session


# Load sent Load IDs from the JSON file
def load_sent_load_ids():
    try:
        with open(LOAD_IDS_FILE, 'r') as file:
            return set(json.load(file))
    except (FileNotFoundError, json.JSONDecodeError):
        return set()

# Save sent Load IDs to the JSON file
def save_sent_load_ids():
    with open(LOAD_IDS_FILE, 'w') as file:
        json.dump(list(sent_load_ids), file)

# Store already sent Load IDs
sent_load_ids = load_sent_load_ids()

# Function to scrape data using an authenticated session
def scrape_data(session):
    try:
        response = session.get(DASHBOARD_URL, headers={
            "User-Agent": "Mozilla/5.0",
            "Referer": LOGIN_API_URL
        })

        if response.status_code != 200:
            print(f"⚠ Failed to load data. Status code: {response.status_code}")
            return []
        print(response.status_code, "111")
        soup = BeautifulSoup(response.content, 'html.parser')
        rows = soup.select("table.datatable tbody tr")
        print(soup, "333")

        data = []
        for row in rows:
            try:
                # Extract the countdown timer (if exists)
                end_time_tag = row.select_one("td:nth-of-type(1) span.countdown")
                if end_time_tag:
                    end_time = int(end_time_tag['data-endtime'])
                    now = int(time.time())
                    interval = end_time - now
                    time_remaining = f"{interval // 60}min {interval % 60}s" if interval > 0 else "Expired"
                else:
                    time_remaining = "Unknown"

                load_id = row.select_one("td:nth-of-type(2) strong").text.strip()
                total_distance = row.select_one("td:nth-of-type(3)").text.strip()
                load_start_date = row.select_one("td:nth-of-type(4)").text.strip()
                load_end_date = row.select_one("td:nth-of-type(5)").text.strip()

                stops_elements = row.select("td:nth-of-type(6) li.stops-item")
                stops = [stop.text.strip() for stop in stops_elements]

                data.append({
                    "Time Remaining": time_remaining,
                    "Load ID": load_id,
                    "Total Distance": total_distance,
                    "Load Start Date": load_start_date,
                    "Load End Date": load_end_date,
                    "Stops": stops
                })
            except Exception as e:
                print(f"Error parsing row: {e}")
        print(data, "+++")
        return data
    except requests.RequestException as e:
        print(f"❌ Request error: {e}")
        return []

# Function to send new data to Telegram
def send_new_data(session):
    global sent_load_ids
    bot.send_message(ADMIN_ID, "🔄 Bot is working and checking for new data...")

    data = scrape_data(session)
    new_data = [item for item in data if item['Load ID'] not in sent_load_ids]
    print(data, "___")
    if not new_data:
        print("✅ No new updates.")
        return

    for item in new_data:
        if item['Time Remaining'] == "Expired":
            sent_load_ids.add(item['Load ID'])
            save_sent_load_ids()
            time.sleep(3)
        else:
            message = (
                "🚛 **New Load Updates:**\n\n"
                f"🕒 Time Remaining: {item['Time Remaining']}\n"
                f"📦 Load ID: `{item['Load ID']}`\n"
                f"📍 Total Distance: {item['Total Distance']}\n"
                f"📆 Load Start Date: {item['Load Start Date']}\n"
                f"📅 Load End Date: {item['Load End Date']}\n"
                f"📌 Stops:\n{chr(10).join(['- ' + stop for stop in item['Stops']])}\n"
            )

            sent_load_ids.add(item['Load ID'])
            save_sent_load_ids()
            time.sleep(3)

            try:
                bot.send_message(TELEGRAM_CHANNEL_ID, message, parse_mode="Markdown")
            except ApiTelegramException as e:
                print(f"⚠ Error sending message: {e}")

def main():
    count = 0
    while True:
        if count == 0:
            session = login_and_get_session()
        send_new_data(session)
        print(f"✅ Checked for new data at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        time.sleep(45)
        count = (count+1) % 8

if __name__ == '__main__':
    main()
