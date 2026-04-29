"""Testovací skript pro ověření připojení k Kimai API."""
import urllib3
import requests
from datetime import datetime, timedelta
from dotenv import load_dotenv, find_dotenv
import os

load_dotenv(find_dotenv())
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

API_KEY = os.getenv('KIMAI_API_TOKEN')

TEST_URLS = [
    "http://192.168.100.8:8001",
]

API_ACTIVITY_SUFFIX = "/api/activities"
API_REPORT_SUFFIX = "/api/timesheets"

HEADERS = {
    "Authorization": f"Bearer {API_KEY}",
    "accept": "application/json"
}


def get_current_user_id(base_url):
    """Získá ID aktuálně přihlášeného uživatele."""
    endpoint = f"{base_url}/api/users/me"
    print("   -> Zjišťuji ID aktuálního uživatele...")
    try:
        response = requests.get(endpoint, headers=HEADERS, verify=False, timeout=10)
        if response.status_code == 200:
            user_data = response.json()
            found_id = user_data.get('id')
            if found_id is not None:
                print(f"   -> Úspěšně získán User ID: {found_id}")
                return found_id

        print(f"   ❌ Nelze získat User ID. Status: {response.status_code}")
        print(f"   Odpověď: {response.text}")
        return None
    except requests.exceptions.RequestException:
        print("   ❌ Chyba při získávání User ID (Connection Error).")
        return None


def test_kimai_connection(base_url):
    """Testuje základní připojení k dané URL."""
    full_url = f"{base_url}{API_ACTIVITY_SUFFIX}"
    print(f"\n--- TESTUJI: {full_url} ---")

    try:
        response = requests.get(full_url, headers=HEADERS, verify=False, timeout=10)
        status = response.status_code

        if status == 200:
            print("✅ STAV: ÚSPĚCH! Připojení a autentizace jsou OK.")
            data = response.json()
            if isinstance(data, list):
                print(f"   Nalezeno {len(data)} aktivit.")
            return True

        if status in [401, 403, 404]:
            print(f"❌ STAV: {status} Chyba přístupu/autentizace/endpointu.")
            print(f"   Odpověď: {response.text[:100]}...")
        else:
            print(f"⚠️ STAV: {status} Jiná chyba serveru. Odpověď: {response.text[:100]}...")

        return False

    except requests.exceptions.Timeout:
        print(f"❌ STAV: Timeout. Server {base_url} neodpověděl včas.")
        return False
    except requests.exceptions.ConnectionError:
        print(f"❌ STAV: Chyba připojení. Server {base_url} je nedostupný.")
        return False
    except requests.exceptions.RequestException as e:
        print(f"❌ STAV: Neočekávaná chyba: {e}")
        return False


def generate_monthly_report(base_url, begin_date, end_date, report_user_id):
    """Generuje měsíční výkaz pro dané období a ID uživatele."""
    full_url = f"{base_url}{API_REPORT_SUFFIX}"

    params = {
        'begin': begin_date.strftime('%Y-%m-%d'),
        'end': end_date.strftime('%Y-%m-%d'),
        'user': report_user_id,
    }

    print(
        f"\n--- GENERUJI VÝKAZ pro období {params['begin']} "
        f"až {params['end']} a User ID {report_user_id} ---"
    )
    print(f"URL dotazu: {full_url}")

    try:
        response = requests.get(
            full_url, headers=HEADERS, params=params, verify=False, timeout=15
        )

        if response.status_code == 200:
            data = response.json()
            total_duration_hours = sum(item.get('duration', 0) for item in data) / 3600

            print("✅ VÝKAZ ÚSPĚŠNĚ ZÍSKÁN!")
            print(f"   Nalezeno {len(data)} časových záznamů.")
            print(f"   Celková odpracovaná doba: {total_duration_hours:.2f} hodin.")

            if data:
                first = data[0]
                activity = first.get('activity', {}).get('name', 'N/A')
                project = first.get('project', {}).get('name', 'N/A')
                print(f"   První záznam: {activity} na projektu {project}")

            return data

        print(f"❌ CHYBA při generování výkazu. Status: {response.status_code}")
        print(f"   Odpověď: {response.text}")
        return None

    except requests.exceptions.RequestException as e:
        print(f"❌ CHYBA PŘIPOJENÍ/DOTAZU: {e}")
        return None


if __name__ == "__main__":
    print(f"Spouštím test připojení k Kimai API pro {len(TEST_URLS)} adresy (Bearer Token).")

    today = datetime.now().date()
    first_of_this_month = today.replace(day=1)
    last_day_of_previous_month = first_of_this_month - timedelta(days=1)
    first_day_of_previous_month = last_day_of_previous_month.replace(day=1)

    functional_url = None
    for test_url in TEST_URLS:
        if test_kimai_connection(test_url):
            functional_url = test_url
            break

    print("\n==============================================")

    if functional_url:
        print(f"FUNKČNÍ ADRESA NALEZENA: {functional_url}")

        user_id = get_current_user_id(functional_url)

        if user_id:
            print("PŘECHÁZÍM NA GENERÁTOR VÝKAZŮ.")
            print(
                f"Generuji výkaz pro období: "
                f"{first_day_of_previous_month} až {last_day_of_previous_month}"
            )
            generate_monthly_report(
                functional_url,
                first_day_of_previous_month,
                last_day_of_previous_month,
                user_id
            )
        else:
            print("❌ NELZE POKRAČOVAT: Nepodařilo se zjistit ID aktuálního uživatele.")
    else:
        print("❌ NEPODAŘILO SE NAVÁZAT FUNKČNÍ PŘIPOJENÍ K ŽÁDNÉ Z TESTOVANÝCH ADRES.")

    print("\n--- TESTY DOKONČENY ---")
