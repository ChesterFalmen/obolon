import requests
import urllib3
import time
from datetime import datetime

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# === Telegram ===
TELEGRAM_TOKEN = "7671763190:AAG_NUGU4ld6Av3DPgNN6CZt7klqNkGfZrI"
CHAT_IDS = ["-1002499902654", "509411504"]

# === Авторизація ===
LOGIN_URL = "https://tms.obolon.ua/api/users/login"
LOGIN_PAYLOAD = {
    "local_ip_addr": "185.244.168.107",
    "user": "akro909",
    "password": "Akro909##"
}

# === Дозволені адреси за f_code_id ===
ALLOWED_CODE_IDS = [8092, 1059, 23178]

# === API Оболонь ===
API_URL = "https://tms.obolon.ua/api/auction/trips?pageSize=100&page=1&fields=win_price,date_closed,fk_trips.full_weight,fk_trips.total_distance,fk_trips.multipoint,currency,date_start,driver,driver_document,f_name_auto,f_name_trailer,descr,time_in,time_delivery,cur_price,date_end,status,show_descr_for_user,f_code_trip,trip_type,start_price,max_price,logist_descr,fk_trip_type.label,fk_currency.code,fk_trips.f_code_trip,fk_trips.total_dist_auc,show_logist_descr_for_user,fk_trips.fk_trip_task.fk_task_org.f_name,fk_trips.fk_trip_task.dist,fk_trips.fk_trip_task.weight,fk_trips.fk_trip_car.f_code_id,fk_trips.fk_trip_car.f_number,fk_trips.fk_trip_car.f_name,manager_full_name,fk_closeator.value,fk_trips.fk_begin_addr.f_name,fk_trips.end_addr_name&filters=[[\"fk_trips.export\",\"eq\",0],[\"auc_type\",\"eq\",0],[\"status\",\"eq\",0],[\"in_queue\",\"eq\",0]]&default_sort=[[\"date_start\",\"DESC\"],[\"fk_trips.trip_id\",\"DESC\"]]"

sent_ids = set()
last_update_time = None
last_trip_count = 0
last_update_id = 0

def send_telegram_message(text, chat_id=None, reply_to_message_id=None):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    targets = [chat_id] if chat_id else CHAT_IDS

    for target_chat in targets:
        payload = {
            "chat_id": target_chat,
            "text": text
        }
        if reply_to_message_id:
            payload["reply_to_message_id"] = reply_to_message_id
        try:
            response = requests.post(url, data=payload)
            if response.status_code != 200:
                print(f"❌ Помилка надсилання в чат {target_chat}:", response.text)
        except Exception as e:
            print(f"❌ Telegram Error для {target_chat}:", e)

def check_for_status_command():
    global last_update_id

    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/getUpdates"
    try:
        response = requests.get(url, params={"offset": last_update_id + 1})
        data = response.json()

        for update in data.get("result", []):
            last_update_id = update["update_id"]
            message = update.get("message", {})
            chat_id = message.get("chat", {}).get("id")
            text = message.get("text", "")
            message_id = message.get("message_id")

            if text.strip().lower() == "/status":
                reply = (
                    "✅ Бот активний\n"
                    f"🕒 Останнє оновлення: 03.04 11:25\n"
                    f"📦 Поточна кількість рейсів: {last_trip_count}"
                )
                send_telegram_message(reply, chat_id=chat_id, reply_to_message_id=message_id)
    except Exception as e:
        print("❌ Помилка під час перевірки /status:", e)

def login():
    session = requests.Session()
    try:
        response = session.post(LOGIN_URL, json=LOGIN_PAYLOAD, verify=False)
        response.raise_for_status()
        print("🔐 Успішно авторизовано")
        return session
    except requests.exceptions.RequestException as e:
        print("❌ Помилка логіну:", e)
        return None

def take_trip(session, trip_data):
    trip_id = trip_data["id"]
    cur_price = trip_data["cur_price"]
    fk_trip_id = trip_data["fk_trips"]["trip_id"]
    url = f"https://tms.obolon.ua/api/auction/trips/update/{trip_id}"

    payload = {
        "id": trip_id,
        "cur_price": cur_price,
        "win_price": cur_price,
        "status": 1,
        "closeator": 65903,
        "manager_full_name": "Дунда Євгеній",
        "fk_currency": {"id": 1, "name": "Гривня", "code": "UAH"},
        "fk_trips": {"trip_id": fk_trip_id}
    }

    try:
        response = session.post(url, json=payload, verify=False)
        if response.status_code == 200:
            print(f"✅ Заявку {trip_id} успішно взято!")
            send_telegram_message(f"✅ Заявка {trip_id} успішно взята!")
        else:
            print(f"❌ Помилка взяття заявки {trip_id}: {response.status_code}")
            print("🔍 Вміст:", response.text)
            send_telegram_message(f"❌ Помилка взяття заявки {trip_id}: {response.status_code}")
    except Exception as e:
        print("❌ Виняток під час взяття:", e)
        send_telegram_message(f"❌ Виняток під час взяття заявки {trip_id}")

def fetch_data(session):
    global last_update_time, last_trip_count

    try:
        response = session.get(API_URL, verify=False)
        if response.status_code == 401:
            print("🔄 Сесія закінчилась. Перелогінюємось...")
            return None

        response.raise_for_status()
        trips = response.json().get("rows", [])
        #print(f"Знайдено рейсів: {len(trips)}")

        last_update_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        last_trip_count = len(trips)

        for trip in trips:
            descr = (trip.get("logist_descr") or "").lower()
            trip_id = trip.get("f_code_trip")
            begin_code = trip.get("fk_trips", {}).get("fk_begin_addr", {}).get("f_code_id")

            if trip_id in sent_ids:
                continue

            if begin_code not in ALLOWED_CODE_IDS:
                continue

            if any(keyword in descr for keyword in ["дробина", "ячмінь", "жито", "зерновоз"]):
                try:
                    total_distance = trip.get("fk_trips", {}).get("total_distance", 0) or 0
                    cur_price = trip.get("cur_price", 0) or 0
                    pdv_price = cur_price * 1.2
                    calc_price = total_distance * 2.35 * 22

                    begin_name = trip.get("fk_trips", {}).get("fk_begin_addr", {}).get("f_name", "—")
                    end_city = trip.get("fk_trips", {}).get("end_addr_name", "—")

                    message = (
                        f"🚛 *Новий рейс знайдено!*\n"
                        f"ID: {trip_id}\n"
                        f"Звідки: {begin_name}\n"
                        f"Куди: {end_city}\n"
                        f"Опис: {trip.get('logist_descr') or '—'}\n"
                        f"Відстань: {total_distance} км\n"
                        f"📦 Ціна з ПДВ: {round(pdv_price)} грн\n"
                        f"📐 Розрахована ціна: {round(calc_price)} грн\n"
                    )

                    if calc_price <= pdv_price:
                        message += "✅ Ціна по формулі <= за ПДВ — заявка буде взята через 2 секунди"
                        send_telegram_message(message)
                        print(f"🕒 Очікуємо 4 секунди перед взяттям {trip_id}...")
                        time.sleep(4)
                        take_trip(session, trip)
                    else:
                        message += "ℹ️ Ціна по формулі нижча — заявку не беремо автоматично"
                        send_telegram_message(message)

                    sent_ids.add(trip_id)

                except Exception as e:
                    print(f"⚠️ Помилка при обробці рейсу {trip_id}:", e)

        return session

    except requests.exceptions.RequestException as e:
        print("❌ Error fetching data:", e)
        return session


# === Головний цикл ===
if __name__ == "__main__":
    session = login()
    print("Останнє оновлення 03.04 11:25")
    while True:
        if session:
            result = fetch_data(session)
            if result is None:
                time.sleep(2)
                session = login()
        else:
            print("⏳ Очікуємо, поки логін спрацює..")
            time.sleep(5)

        check_for_status_command()
        time.sleep(5)
