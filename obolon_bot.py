import requests
import urllib3
import time
from datetime import datetime
import threading

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# === Telegram ===
#TELEGRAM_TOKEN = "8044263077:AAE8HTKA_FxPBLLAaYcV5xpNOWC9hCpI4Yo" # зерновоз2
TELEGRAM_TOKEN = "7671763190:AAG_NUGU4ld6Av3DPgNN6CZt7klqNkGfZrI" # зерновоз
CHAT_IDS = ["-1002499902654", "509411504"]

# === Авторизація ===
LOGIN_URL = "https://tms.obolon.ua/api/users/login"
LOGIN_PAYLOAD = {
    "local_ip_addr": "185.244.168.107",
    "user": "akro909",
    "password": "Akro909##"
}

# === Дозволені адреси за f_code_id ==
ALLOWED_CODE_IDS = [8092, 1059, 23178]

# === API URL ===
#API_URL = "http://localhost:3000/api/routes"
API_URL = "https://tms.obolon.ua/api/auction/trips?pageSize=100&page=1&fields=win_price,date_closed,fk_trips.full_weight,fk_trips.total_distance,fk_trips.multipoint,currency,date_start,driver,driver_document,f_name_auto,f_name_trailer,descr,time_in,time_delivery,cur_price,date_end,status,show_descr_for_user,f_code_trip,trip_type,start_price,max_price,logist_descr,fk_trip_type.label,fk_currency.code,fk_trips.f_code_trip,fk_trips.total_dist_auc,show_logist_descr_for_user,fk_trips.fk_trip_task.fk_task_org.f_name,fk_trips.fk_trip_task.dist,fk_trips.fk_trip_task.weight,fk_trips.fk_trip_car.f_code_id,fk_trips.fk_trip_car.f_number,fk_trips.fk_trip_car.f_name,manager_full_name,fk_closeator.value,fk_trips.fk_begin_addr.f_name,fk_trips.end_addr_name&filters=[[\"fk_trips.export\",\"eq\",0],[\"auc_type\",\"eq\",0],[\"status\",\"eq\",0],[\"in_queue\",\"eq\",0]]&default_sort=[[\"date_start\",\"DESC\"],[\"fk_trips.trip_id\",\"DESC\"]]"
# === Стан ===
monitored_ids = {}
last_update_time = "-"
last_trip_count = 0

def send_telegram_message(text, chat_id=None):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"

    targets = [chat_id] if chat_id else CHAT_IDS

    for target in targets:
        payload = {"chat_id": target, "text": text, "parse_mode": "Markdown"}
        try:
            response = requests.post(url, data=payload)
            if response.status_code != 200:
                print(f"❌ Помилка надсилання в чат {target}:", response.text)
        except Exception as e:
            print(f"❌ Telegram Error для {target}:", e)

def login():
    session = requests.Session()
    try:
        session.post(LOGIN_URL, json=LOGIN_PAYLOAD, verify=False)
        print("🔐 Успішно авторизовано")
        return session
    except Exception as e:
        now = datetime.now()
        formatted_time = now.strftime("%Y-%m-%d %H:%M:%S")
        print(formatted_time, " | ❌ Помилка логіну:", e)
        return None

def take_trip(session, trip):
    trip_id = trip["id"]
    cur_price = trip["cur_price"]
    fk_trip_id = trip["fk_trips"]["trip_id"]

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

    url = f"https://tms.obolon.ua/api/auction/trips/update/{trip_id}"
    now = datetime.now()
    formatted_time = now.strftime("%Y-%m-%d %H:%M:%S")
    try:
        response = session.post(url, json=payload, verify=False)
        if response.status_code == 200:
            print(f"{formatted_time} | ✅ Заявку {trip_id} успішно взято!")
            send_telegram_message(f"✅ Заявка #{trip_id} успішно взята!")
            monitored_ids.pop(trip_id, None)
            time.sleep(3)
        else:
            send_telegram_message(f"❌ Помилка взяття заявки {trip_id}: {response.status_code}")
    except Exception as e:
        send_telegram_message(f"❌ Виняток при взятті заявки {trip_id}: {e}")

def handle_status_command(chat_id):
    send_telegram_message(f"📊 Статус бота\nОновлено: {last_update_time}\nРейсів: {last_trip_count}", chat_id)

def handle_monitoring_command(chat_id):
    print(f"📥 Команда /monitoring отримана від чату: {chat_id}")
    print(f"🔎 Зараз у monitored_ids: {len(monitored_ids)} елементів")

    if not monitored_ids:
        send_telegram_message("📭 Моніторинг порожній.", chat_id)
        return

    msg = f"🕵 У моніторингу {len(monitored_ids)} заявок:\n"
    for tid, data in monitored_ids.items():
        try:
            dist = data.get("dist", 0)
            pdv = round(data["pdv_price"])
            calc = round(data["calc_price"])
            from_city = data.get("from", "—")
            to_city = data.get("to", "—")

            try:
                per_km = pdv / 22 / dist if dist else 0
                per_ton = pdv / 22
                per_km_total = pdv / dist if dist else 0
            except ZeroDivisionError:
                per_km = per_ton = per_km_total = 0

            msg += (
                f"• ID: {tid} | {dist} км\n\n"
                f"🏁 Звідки: {from_city}\n"
                f"🎯 Куди: {to_city}\n"
                f"📦 Поточна ціна з ПДВ: *{pdv}* грн\n"
                f"📐 Очікувана: *{calc}* грн\n"
                f"📊 Ціна за км/т: `{per_km:.2f}` грн/т/км\n"
                f"⚖️ Ціна за тону: `{per_ton:.2f}` грн/т\n"
                f"🛣️ Ціна за км: `{per_km_total:.2f}` грн/км\n\n"
            )

        except Exception as e:
            print(f"⚠️ Помилка при обробці заявки {tid}: {e}")

    print("📤 Надсилаємо повідомлення в Telegram...")
    send_telegram_message(msg, chat_id)


def fetch_data(session):
    global last_update_time, last_trip_count

    try:
        response = session.get(API_URL, verify=False)
        if response.status_code == 401:
            return None

        data = response.json()
        trips = data.get("rows", [])
        last_update_time = datetime.now().strftime("%d.%m.%Y %H:%M")
        last_trip_count = len(trips)

        for trip in trips:
            trip_id = trip.get("f_code_trip")
            descr = (trip.get("logist_descr") or '').lower()
            begin = trip.get("fk_trips", {}).get("fk_begin_addr", {})
            begin_id = begin.get("f_code_id")

            if begin_id not in ALLOWED_CODE_IDS:
                continue
            if not any(k in descr for k in ["дробина", "ячмінь", "зерновоз"]):
                continue

            dist = trip.get("fk_trips", {}).get("total_distance", 0) or 0
            cur = trip.get("cur_price", 0) or 0
            pdv = cur * 1.2
            calc = dist * 2.35 * 22

            if trip_id not in monitored_ids:
                send_telegram_message(
                    f"🚛 *Новий рейс додано у моніторинг!* "
                    f"ID: {trip_id}\n"
                    f"Звідки: {begin.get('f_name')}\n"
                    f"Куди: {trip.get('fk_trips', {}).get('end_addr_name')}\n"
                    f"Відстань: {dist} км\n"
                    f"Коментар: {descr}\n"
                    f"Ціна з ПДВ: {round(pdv)} грн\n"
                    f"Очікувана мін. ціна: {round(calc)} грн"
                )

            monitored_ids[trip_id] = {
                "calc_price": calc,
                "pdv_price": pdv,
                "dist": dist,
                "trip": trip,
                "from": begin.get('f_name'),
                "to": trip.get('fk_trips', {}).get('end_addr_name')
            }

            if pdv >= calc:
                send_telegram_message(f"✅ Ціна по ПДВ ({round(pdv)} грн) >= розрахованої ({round(calc)} грн)\n"
                                      f"Беремо {trip_id} через 4 секунди")
                monitored_ids.pop(trip_id, None)
                time.sleep(4)
                take_trip(session, trip)

        return session
    except Exception as e:
        now = datetime.now()
        formatted_time = now.strftime("%Y-%m-%d %H:%M:%S")
        print(formatted_time, " | ❌ Error fetching:", e)
        return session

def telegram_listener():
    offset = None
    while True:
        try:
            url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/getUpdates"
            if offset:
                url += f"?offset={offset}"
            updates = requests.get(url).json().get("result", [])
            for u in updates:
                offset = u["update_id"] + 1
                msg = u.get("message", {})
                text = msg.get("text", "")
                chat_id = msg.get("chat", {}).get("id")

                if text == "/status":
                    handle_status_command()  # Можеш теж оновити, якщо хочеш персоналізувати
                elif text == "/monitoring":
                    handle_monitoring_command(chat_id)
        except Exception as e:
            print("❌ Telegram error:", e)
        time.sleep(3)

# === MAIN ===
if __name__ == "__main__":
    session = login()
    threading.Thread(target=telegram_listener, daemon=True).start()
    while True:
        if session:
            session = fetch_data(session) or login()
        else:
            session = login()
        time.sleep(5)
