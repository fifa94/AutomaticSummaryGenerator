import requests
import json
import urllib3
from datetime import datetime, timedelta # Nový import pro práci s daty
from dotenv import load_dotenv, find_dotenv
import os

# Načte .env (hledá v aktuálním adresáři a výše)
load_dotenv(find_dotenv())
# Vypneme varování o neověřeném SSL certifikátu, pokud bychom omylem použili HTTPS na self-signed certifikát
# Pro HTTP to nemá vliv.
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)


## 🛠️ KONFIGURACE
# --- ZMĚŇTE NA SVÉ SKUTEČNÉ HODNOTY ---
# UŽIVATELSKÉ JMÉNO již není potřeba, pokud používáme Bearer Token
USERNAME = "admin" # Ponecháme jako referenci
# TENTO KLÍČ/TOKEN JE TEN, KTERÝ FUNGOVAL V POSTMANU JAKO "BEARER TOKEN"
API_KEY = os.getenv('KIMAI_API_TOKEN')
# -----------------------------

import requests
import json
import urllib3
from datetime import datetime, timedelta # Nový import pro práci s daty
from dotenv import load_dotenv, find_dotenv
import os

# Načte .env (hledá v aktuálním adresáři a výše)
load_dotenv(find_dotenv())
# Vypneme varování o neověřeném SSL certifikátu, pokud bychom omylem použili HTTPS na self-signed certifikát
# Pro HTTP to nemá vliv.
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)


## 🛠️ KONFIGURACE
# --- ZMĚŇTE NA SVÉ SKUTEČNÉ HODNOTY ---
# UŽIVATELSKÉ JMÉNO již není potřeba, pokud používáme Bearer Token
USERNAME = "admin" # Ponecháme jako referenci
# TENTO KLÍČ/TOKEN JE TEN, KTERÝ FUNGOVAL V POSTMANU JAKO "BEARER TOKEN"
API_KEY = os.getenv('KIMAI_API_TOKEN')
# -----------------------------

# Seznam adres, které chceme otestovat
TEST_URLS = [
    # 1. Lokální adresa (Včetně portu a protokolu HTTP)
    "http://192.168.100.8:8001",
]

# Koncový bod pro základní test
API_ACTIVITY_SUFFIX = "/api/activities"
# Koncový bod pro výkaz
API_REPORT_SUFFIX = "/api/timesheets"


# Vytvoření hlaviček PRO BEARER TOKEN AUTENTIZACI
HEADERS = {
    "Authorization": f"Bearer {API_KEY}", # Standardní hlavička pro Bearer token
    "accept": "application/json"
}

def get_current_user_id(base_url):
    """
    Získá ID aktuálně přihlášeného uživatele pomocí endpointu /api/users/me.
    """
    url = f"{base_url}/api/users/me"
    print("   -> Zjišťuji ID aktuálního uživatele...")
    try:
        response = requests.get(url, headers=HEADERS, verify=False, timeout=10)
        if response.status_code == 200:
            user_data = response.json()
            user_id = user_data.get('id')
            if user_id is not None:
                print(f"   -> Úspěšně získán User ID: {user_id}")
                return user_id

        print(f"   ❌ Nelze získat User ID. Status: {response.status_code}")
        print(f"   Odpověď: {response.text}")
        return None
    except requests.exceptions.RequestException:
        print("   ❌ Chyba při získávání User ID (Connection Error).")
        return None

def test_kimai_connection(base_url):
    """
    Testuje základní připojení k dané základní URL (endpoint /api/activities).
    """
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
                return True # Vracíme True, pokud je spojení funkční
            return True

        elif status in [401, 403, 404]:
            print(f"❌ STAV: {status} Chyba přístupu/autentizace/endpointu.")
            print(f"   CHYBA: Viz chybová hláška. Odpověď: {response.text[:100]}...")
        else:
            print(f"⚠️ STAV: {status} Jiná chyba serveru. Odpověď: {response.text[:100]}...")

        return False # Vracíme False, pokud je chyba

    except requests.exceptions.Timeout:
        print(f"❌ STAV: Timeout. Server {base_url} neodpověděl včas.")
        return False
    except requests.exceptions.ConnectionError:
        print(f"❌ STAV: Chyba připojení. Server {base_url} je nedostupný.")
        return False
    except Exception as e:
        print(f"❌ STAV: Neočekávaná chyba: {e}")
        return False


def generate_monthly_report(base_url, begin_date, end_date, user_id):
    """
    Generuje měsíční výkaz pro dané období a ID uživatele.
    """
    full_url = f"{base_url}{API_REPORT_SUFFIX}"

    # Parametry pro filtrování časových záznamů (Nyní včetně user_id!)
    params = {
        'begin': begin_date.strftime('%Y-%m-%d'),
        'end': end_date.strftime('%Y-%m-%d'),
        'user': user_id, # KLÍČOVÝ FILTR PRO OPRAVU 400 Bad Request
    }

    print(f"\n--- GENERUJI VÝKAZ pro období {params['begin']} až {params['end']} a User ID {user_id} ---")
    print(f"URL dotazu: {full_url}")

    try:
        response = requests.get(full_url, headers=HEADERS, params=params, verify=False, timeout=15)

        if response.status_code == 200:
            data = response.json()
            total_duration_seconds = sum(item.get('duration', 0) for item in data)
            total_duration_hours = total_duration_seconds / 3600

            print(f"✅ VÝKAZ ÚSPĚŠNĚ ZÍSKÁN!")
            print(f"   Nalezeno {len(data)} časových záznamů.")
            print(f"   Celková odpracovaná doba: {total_duration_hours:.2f} hodin.")

            # Příklad prvního záznamu pro kontrolu struktury
            if data:
                first = data[0]
                print(f"   První záznam: {first.get('activity', {}).get('name', 'N/A')} na projektu {first.get('project', {}).get('name', 'N/A')}")

            return data
        else:
            print(f"❌ CHYBA při generování výkazu. Status: {response.status_code}")
            print(f"   Odpověď: {response.text}")
            return None

    except requests.exceptions.RequestException as e:
        print(f"❌ CHYBA PŘIPOJENÍ/DOTAZU: {e}")
        return None


if __name__ == "__main__":
    print(f"Spouštím test připojení k Kimai API pro {len(TEST_URLS)} adresy (Bearer Token).")

    # 1. Spočítáme datum pro předchozí měsíc (pro účely ukázky)
    today = datetime.now().date()
    first_of_this_month = today.replace(day=1)
    last_day_of_previous_month = first_of_this_month - timedelta(days=1)
    first_day_of_previous_month = last_day_of_previous_month.replace(day=1)

    # Nejprve provedeme test základní konektivity
    functional_url = None
    for url in TEST_URLS:
        if test_kimai_connection(url):
            functional_url = url
            break

    print("\n==============================================")

    if functional_url:
        print(f"FUNKČNÍ ADRESA NALEZENA: {functional_url}")

        # NOVÝ KROK: Získání ID uživatele
        user_id = get_current_user_id(functional_url)

        if user_id:
            print("PŘECHÁZÍM NA GENERÁTOR VÝKAZŮ.")
            print(f"Generuji výkaz pro období: {first_day_of_previous_month} až {last_day_of_previous_month}")

            # 2. Generování výkazu na funkční adrese, nyní s ID uživatele
            generate_monthly_report(
                functional_url,
                first_day_of_previous_month,
                last_day_of_previous_month,
                user_id # Předání ID uživatele
            )
        else:
            print("❌ NELZE POKRAČOVAT: Nepodařilo se zjistit ID aktuálního uživatele.")
    else:
        print("❌ NEPODAŘILO SE NAVÁZAT FUNKČNÍ PŘIPOJENÍ K ŽÁDNÉ Z TESTOVANÝCH ADRES.")
        print("Opravte chybu 403/401 nebo chybu připojení (ConnectionError/Timeout).")

    print("\n--- TESTY DOKONČENY ---")