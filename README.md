# Automatic Summary Generator

Webová aplikace pro správu a odesílání automatických měsíčních výkazů odpracované doby ze systému Kimai.

## Funkce

- 📊 **Webové UI** - Moderní interface pro správu reportů
- 📋 **Náhled reportu** - Vidíte přesně jak bude výkaz vypadat
- 📅 **Plánování** - Nastavte den a čas odesílání
- 👥 **Správa příjemců** - Přidávejte/odebírejte emailové adresy
- 💰 **Hodinová sazba** - Nastavit si cenu za hodinu práce
- 📜 **Historie** - Přehled všech odeslaných reportů
- 🔄 **Zaokrouhlení** - Automatické zaokrouhlení na 15minut s vyrovnáním

## Tech Stack

- **Backend**: Flask (Python 3.12)
- **Frontend**: HTML5, CSS3, JavaScript
- **Database**: SQLite
- **API**: Kimai Time Tracking

## Instalace

### Lokální spuštění

```bash
# 1. Vytvoř virtuální prostředí
python -m venv venv
source venv/bin/activate  # Linux/Mac
# nebo
venv\Scripts\activate  # Windows

# 2. Nainstaluj závislosti
pip install -r requirements.txt

# 3. Nastav .env (kopíruj z .env.example)
cp .env.example .env

# 4. Spusť aplikaci
python app.py
```

Aplikace bude běžet na `http://localhost:5000`

### Docker

```bash
# 1. Build image
docker build -t automatic-summary-generator:latest .

# 2. Spusť kontejner
docker run -p 5000:5000 --env-file .env automatic-summary-generator:latest
```

## Konfigurace

Vytvoř soubor `.env` s následujícím obsahem:

```env
KIMAI_API_TOKEN=tvůj_api_token
KIMAI_API_URL=http://kimai-host:8001/api/timesheets
KIMAI_ACTIVITIES_URL=http://kimai-host:8001/api/activities
KIMAI_PROJECT_TITLE=Název Projektu

SMTP_USER=tvůj_email@gmail.com
SMTP_PASS=tvoje_app_heslo
SMTP_TO=prijem@example.com
```

## Použití

1. **Otevři aplikaci** na http://localhost:5000
2. **Nastav parametry**:
   - Den odesílání v měsíci
   - Čas odesílání
   - Hodinová sazba
   - Email příjemci
3. **Klikni na "Náhled finálního reportu"** pro náhled
4. **Klikni na "Odeslat report nyní"** pro okamžité odeslání

## API Endpoints

- `GET /` - Hlavní stránka
- `GET /api/config` - Načti konfiguraci
- `POST /api/config` - Ulož konfiguraci
- `GET /api/preview` - Náhled dat z Kimai
- `GET /api/preview-full` - Kompletní HTML náhled reportu
- `POST /api/send-report` - Odešli report
- `GET /api/history` - Historie reportů

## Soubory

- `app.py` - Flask aplikace
- `database.py` - SQLite databáze
- `ApiScraperFromKimai.py` - Skraper Kimai API
- `templates/index.html` - Web UI
- `Dockerfile` - Docker konfiguraci
- `requirements.txt` - Python závislosti

## Konfigurace identity reportu

Osobní údaje ve výkazu se nastavují přes env proměnné (viz níže), aby nebyly natvrdo v kódu:

```env
REPORT_WORKER_FULLNAME=Ing. Jméno Příjmení
REPORT_WORKER_SIGNNAME=Jméno Příjmení
REPORT_EMPLOYER=Název zaměstnavatele
REPORT_SUPERVISOR=Mgr. Nadřízený
REPORT_AGREEMENT_NO=1/2025
REPORT_AGREEMENT_DATE=11.11.2025
REPORT_CITY=Praze
```

## Licenza

MIT
