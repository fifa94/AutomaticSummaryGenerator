from flask import Flask, render_template, request, jsonify
from flask_cors import CORS
from datetime import datetime, timedelta
import os
import requests
from dotenv import load_dotenv, find_dotenv
from apscheduler.schedulers.background import BackgroundScheduler
from ApiScraperFromKimai import (
    ApiScraperFromKimai, DocumentGenerator, SendEmail,
    WORKER_FULLNAME, WORKER_SIGNNAME, EMPLOYER_NAME, SUPERVISOR_NAME,
    AGREEMENT_NO, AGREEMENT_DATE, REPORT_CITY,
    PROJECT_TITLE, activity_matches_project,
)
from database import (
    get_config, save_config, get_report_history, add_report_history,
    has_successful_send_this_month,
)

load_dotenv(find_dotenv())

app = Flask(__name__)
CORS(app)

def get_kimai_hosts():
    """Sestaví seznam Kimai base URL z env (KIMAI_HOSTS, KIMAI_API_URL) + fallback."""
    hosts = []
    env_hosts = os.getenv('KIMAI_HOSTS')
    if env_hosts:
        hosts += [h.strip().rstrip('/') for h in env_hosts.split(',') if h.strip()]
    api_url = os.getenv('KIMAI_API_URL')
    if api_url:
        base = api_url.rstrip('/')
        for suffix in ('/api/timesheets', '/api/activities'):
            if base.endswith(suffix):
                base = base[:-len(suffix)]
        hosts.append(base.rstrip('/'))
    hosts += ["http://192.168.100.8:8001", "http://192.168.191.211:8001"]
    seen, result = set(), []
    for h in hosts:
        if h and h not in seen:
            seen.add(h)
            result.append(h)
    return result

URL_LIST = get_kimai_hosts()

BEARER_TOKEN = os.getenv('KIMAI_API_TOKEN')
OUTPUT_DIR = os.getenv('OUTPUT_DIR', '/app/output')

CZECH_MONTHS = {
    1:  'leden',
    2:  'únor',
    3:  'březen',
    4:  'duben',
    5:  'květen',
    6:  'červen',
    7:  'červenec',
    8:  'srpen',
    9:  'září',
    10: 'říjen',
    11: 'listopad',
    12: 'prosinec'
}

def is_host_reachable(url, timeout=3):
    import requests
    try:
        requests.get(url, timeout=timeout)
        return True
    except requests.exceptions.RequestException:
        return False

def get_active_host():
    for url in URL_LIST:
        if is_host_reachable(url):
            return url
    return None

def duration_to_hours(dur: str) -> float:
    dur = dur.strip()
    parts = dur.split(':')
    if len(parts) != 2:
        return 0
    hours, minutes = parts
    return int(hours) + (int(minutes) / 60)

def parse_period(start_str, end_str):
    """Z řetězců YYYY-MM-DD vrátí (start_date, end_date) nebo (None, None)."""
    if not start_str or not end_str:
        return None, None
    start = datetime.strptime(start_str, '%Y-%m-%d').date()
    end = datetime.strptime(end_str, '%Y-%m-%d').date()
    if start > end:
        start, end = end, start
    return start, end

def no_data_message(scraper, period_start, period_end):
    start, end = scraper._resolve_period(period_start, period_end)
    return f"Žádné záznamy v Kimai za období {start:%d.%m.%Y} – {end:%d.%m.%Y}"

def generate_and_send_report(period_start=None, period_end=None):
    """Vygeneruje a odešle report příjemcům z konfigurace.

    Vrací (success: bool, message: str). Zapisuje záznam do historie.
    """
    config = get_config()

    if not config['recipients']:
        add_report_history([], 'failed', error_message='Nejsou nastaveni příjemci')
        return False, 'Nejsou nastaveni příjemci'

    active_host = get_active_host()
    if not active_host:
        add_report_history(config['recipients'], 'failed', error_message='Nelze se připojit k Kimai')
        return False, 'Nelze se připojit k Kimai'

    scraper = ApiScraperFromKimai(active_host, BEARER_TOKEN, 'admin')
    data = scraper.process_timesheets(period_start=period_start, period_end=period_end)

    if not data:
        message = no_data_message(scraper, period_start, period_end)
        add_report_history(config['recipients'], 'failed', error_message=message)
        return False, message

    document = DocumentGenerator(data, config['hourly_rate'])
    document.generate_document()
    file_name = document.get_file_name()

    if not file_name:
        add_report_history(config['recipients'], 'failed', error_message='Nepodařilo se vytvořit dokument')
        return False, 'Nepodařilo se vytvořit dokument'

    smtp_user = os.getenv('SMTP_USER')
    smtp_pass = os.getenv('SMTP_PASS')

    if not (smtp_user and smtp_pass):
        add_report_history(config['recipients'], 'failed', error_message='SMTP není konfigurován')
        return False, 'SMTP není konfigurován'

    email = SendEmail("smtp.gmail.com", 587, smtp_user, smtp_pass)

    for recipient in config['recipients']:
        if not email.send_email(file_name, recipient):
            add_report_history(config['recipients'], 'partial_failed',
                               file_name=os.path.basename(file_name),
                               error_message=f'Selhání při odeslání {recipient}')
            return False, f'Selhání při odeslání {recipient}'

    add_report_history(config['recipients'], 'success', file_name=os.path.basename(file_name))
    return True, os.path.basename(file_name)

def seed_config_from_env():
    """Při prvním spuštění (prázdná konfigurace) předvyplní příjemce z env SMTP_TO."""
    config = get_config()
    if config['recipients']:
        return
    smtp_to = os.getenv('SMTP_TO')
    if not smtp_to:
        return
    recipients = [r.strip() for r in smtp_to.split(';') if r.strip()]
    if recipients:
        save_config(config['schedule_day'], config['schedule_time'],
                    recipients, config['enabled'], config['hourly_rate'])
        print(f"Konfigurace předvyplněna z env SMTP_TO: {recipients}")

def scheduled_check():
    """Spouští se každou minutu; odešle report v nastavený den a čas."""
    config = get_config()
    if not config['enabled']:
        return
    now = datetime.now()
    if now.day != config['schedule_day']:
        return
    if now.strftime('%H:%M') != config['schedule_time']:
        return
    if has_successful_send_this_month():
        print("Report už byl tento měsíc odeslán — přeskakuji.")
        return
    print(f"Plánované odeslání reportu v {now.strftime('%d.%m.%Y %H:%M')}")
    success, message = generate_and_send_report()
    print(f"Výsledek plánovaného odeslání: {success} — {message}")

@app.route('/')
def index():
    """Hlavní stránka."""
    config = get_config()
    history = get_report_history(10)
    return render_template('index.html', config=config, history=history)

@app.route('/api/config', methods=['GET'])
def get_config_api():
    """Vrátí aktuální konfiguraci."""
    return jsonify(get_config())

@app.route('/api/config', methods=['POST'])
def save_config_api():
    """Uloží konfiguraci."""
    data = request.json
    schedule_day = int(data.get('schedule_day', 1))
    schedule_time = data.get('schedule_time', '08:00')
    recipients = data.get('recipients', [])
    enabled = data.get('enabled', True)
    hourly_rate = float(data.get('hourly_rate', 350))

    if schedule_day < 1 or schedule_day > 31:
        return jsonify({'error': 'Den musí být 1-31'}), 400

    if not recipients:
        return jsonify({'error': 'Musí být zadán alespoň jeden příjemce'}), 400

    if hourly_rate <= 0:
        return jsonify({'error': 'Hodinová sazba musí být větší než 0'}), 400

    save_config(schedule_day, schedule_time, recipients, enabled, hourly_rate)

    return jsonify({'success': True, 'message': 'Konfigurace uložena'})

@app.route('/api/preview', methods=['GET'])
def preview_report():
    """Vrátí data pro náhled."""
    try:
        period_start, period_end = parse_period(request.args.get('start'), request.args.get('end'))
        active_host = get_active_host()
        if not active_host:
            return jsonify({'error': 'Nelze se připojit k Kimai'}), 500

        scraper = ApiScraperFromKimai(active_host, BEARER_TOKEN, 'admin')
        data = scraper.process_timesheets(period_start=period_start, period_end=period_end)

        if not data:
            return jsonify({'error': no_data_message(scraper, period_start, period_end)}), 404

        preview_data = []
        for row in data:
            preview_data.append({
                'date': row['Date'].strftime('%d.%m.%Y'),
                'from': row['From'],
                'to': row['To'],
                'duration': row['Duration']
            })

        return jsonify({'data': preview_data})

    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/preview-full', methods=['GET'])
def preview_full_report():
    """Vrátí kompletní HTML náhled reportu."""
    try:
        config = get_config()
        period_start, period_end = parse_period(request.args.get('start'), request.args.get('end'))
        active_host = get_active_host()
        if not active_host:
            return jsonify({'error': 'Nelze se připojit k Kimai'}), 500

        scraper = ApiScraperFromKimai(active_host, BEARER_TOKEN, 'admin')
        data = scraper.process_timesheets(period_start=period_start, period_end=period_end)

        if not data:
            return jsonify({'error': no_data_message(scraper, period_start, period_end)}), 404

        heading_month = CZECH_MONTHS[data[0]["Date"].month]
        doc_year = data[0]["Date"].year
        report_month = data[0]["Date"].month
        report_year = data[0]["Date"].year

        if report_month == 12:
            last_day_of_month = datetime(report_year, 12, 31)
        else:
            first_of_next = datetime(report_year, report_month + 1, 1)
            last_day_of_month = first_of_next - timedelta(days=1)

        sign_date = last_day_of_month.strftime('%d.%m.%Y')

        worked_hours = 0
        table_rows = ""

        for row in data:
            formatted_date = row["Date"].strftime('%d.%m.%Y')
            duration_hours = duration_to_hours(row['Duration'])
            worked_hours += duration_hours

            if duration_hours > 0:
                table_rows += f"""
            <tr>
                <td>{formatted_date}</td>
                <td>{row['From']} – {row['To']}</td>
                <td>{duration_hours:.2f}</td>
            </tr>
            """

        total_price = worked_hours * config['hourly_rate']

        html = f"""
        <!DOCTYPE html>
        <html lang="cs">
        <head>
            <meta charset="UTF-8">
            <title>Výkaz odpracované doby</title>
            <style>
                body {{
                    font-family: Arial, sans-serif;
                    max-width: 900px;
                    margin: 40px auto;
                    padding: 20px;
                    line-height: 1.6;
                    color: #333;
                }}
                h1 {{
                    font-size: 18px;
                    text-align: center;
                    margin-bottom: 30px;
                }}
                .info {{
                    margin-bottom: 20px;
                    font-size: 14px;
                    line-height: 1.8;
                }}
                .worker {{
                    margin-bottom: 20px;
                    font-weight: bold;
                }}
                table {{
                    width: 100%;
                    border-collapse: collapse;
                    margin-bottom: 30px;
                }}
                th, td {{
                    border: 1px solid #333;
                    padding: 12px;
                    text-align: left;
                }}
                th {{
                    background: #f0f0f0;
                    font-weight: bold;
                }}
                .total-row {{
                    font-weight: bold;
                    background: #f9f9f9;
                }}
                .signature {{
                    margin-top: 30px;
                    font-size: 14px;
                }}
                .section {{
                    margin-bottom: 30px;
                    border-bottom: 1px solid #ddd;
                    padding-bottom: 30px;
                }}
                .price {{
                    font-weight: bold;
                    color: #d9534f;
                }}
            </style>
        </head>
        <body>
            <h1>Výkaz odpracované doby zaměstnancem u dohody o pracovní činnosti za měsíc {heading_month} roku {doc_year}</h1>

            <div class="info">
                <p>Práce je po dohodě smluvních stran vykonávána na dálku. V souladu s § 87a zákoníku práce si bude zaměstnanec pracovní dobu do směn při práci na dálku rozvrhovat sám, práce nebude vykonávána ve dnech svátků, víkendů a v čase od 22:00 do 6:00 hod. Délka směny nesmí přesáhnout 12 hodin. Zároveň se zaměstnanec zavazuje, že při práci na dálku bude dodržovat příslušná ustanovení zákoníku práce upravující přestávky v práci a nepřetržitého denního a týdenního odpočinku.</p>
            </div>

            <div class="worker">Zaměstnanec: {WORKER_FULLNAME}</div>

            <table>
                <thead>
                    <tr>
                        <th>Datum</th>
                        <th>V čase od:do (včetně uvedení času přestávky)</th>
                        <th>Počet hodin</th>
                    </tr>
                </thead>
                <tbody>
                    {table_rows}
                    <tr class="total-row">
                        <td colspan="2">Počet hodin odpracovaných celkem/měsíc</td>
                        <td>{worked_hours:.2f}</td>
                    </tr>
                </tbody>
            </table>

            <div class="section">
                <div class="signature">
                    <p>V {REPORT_CITY} dne {sign_date}</p>
                    <p style="margin-top: 40px;">Podpis zaměstnance: {WORKER_SIGNNAME}</p>
                </div>
            </div>

            <div class="section">
                <p><strong>Potvrzení o převzetí dokončené práce na základě dohody o pracovní činnosti č. {AGREEMENT_NO} za měsíc {heading_month} roku {doc_year}.</strong></p>

                <p>Práci, k níž se <strong>{WORKER_FULLNAME}</strong> zavázal na základě dohody ze dne {AGREEMENT_DATE}, převzal odpovědný pracovník {EMPLOYER_NAME}, {SUPERVISOR_NAME}, ve sjednaném rozsahu a kvalitě. Při provedení práce bylo odpracováno celkem <strong>{worked_hours:.2f} hodin</strong>. K výplatě dle dohody náleží pracovníkovi částka ve výši <span class="price">{total_price:.2f} Kč</span>.</p>
            </div>

            <div class="section">
                <div class="signature">
                    <p>V {REPORT_CITY} dne {sign_date}</p>
                    <p style="margin-top: 40px;">Podpis odpovědného pracovníka:</p>
                </div>
            </div>

            <div>
                <p>Kontrola a proplacení provedeno dne _____________________ podpis: _____________________</p>
            </div>
        </body>
        </html>
        """

        return jsonify({
            'html': html,
            'worked_hours': worked_hours,
            'total_price': total_price,
            'hourly_rate': config['hourly_rate']
        })

    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/send-report', methods=['POST'])
def send_report():
    """Okamžitě odešle report. Volitelně za zadané období (start, end)."""
    try:
        data = request.get_json(silent=True) or {}
        period_start, period_end = parse_period(data.get('start'), data.get('end'))
        success, message = generate_and_send_report(period_start=period_start, period_end=period_end)
        if success:
            return jsonify({'success': True, 'message': 'Report úspěšně odeslán', 'file': message})
        return jsonify({'error': message}), 400
    except Exception as e:
        add_report_history([], 'failed', error_message=str(e))
        return jsonify({'error': f'Chyba: {str(e)}'}), 500

@app.route('/api/diagnostics', methods=['GET'])
def diagnostics():
    """Ověří dostupnost Kimai a vrátí, kde případně vázne spojení."""
    result = {'project_title': PROJECT_TITLE or '(všechny projekty)',
              'token_set': bool(BEARER_TOKEN), 'hosts': []}
    headers = {'Authorization': f'Bearer {BEARER_TOKEN}'}
    for host in URL_LIST:
        entry = {'host': host}
        try:
            r = requests.get(host, timeout=3)
            entry['root_status'] = r.status_code
        except Exception as e:
            entry['root_error'] = str(e)
            result['hosts'].append(entry)
            continue
        try:
            r = requests.get(f"{host}/api/timesheets", headers=headers, params={'size': 1}, timeout=5)
            entry['timesheets_status'] = r.status_code
        except Exception as e:
            entry['timesheets_error'] = str(e)
        try:
            r = requests.get(f"{host}/api/activities", headers=headers, timeout=5)
            entry['activities_status'] = r.status_code
            if r.status_code == 200:
                acts = r.json()
                entry['activities_total'] = len(acts)
                entry['activities_matching_project'] = sum(
                    1 for a in acts if activity_matches_project(a)
                )
        except Exception as e:
            entry['activities_error'] = str(e)
        result['hosts'].append(entry)
    return jsonify(result)

@app.route('/api/debug-timesheets', methods=['GET'])
def debug_timesheets():
    """Ukáže trychtýř filtrů — proč případně nejsou data."""
    try:
        period_start, period_end = parse_period(request.args.get('start'), request.args.get('end'))
        active_host = get_active_host()
        if not active_host:
            return jsonify({'error': 'Nelze se připojit k Kimai'}), 500

        scraper = ApiScraperFromKimai(active_host, BEARER_TOKEN, 'admin')
        start_date, end_date = scraper._resolve_period(period_start, period_end)
        active_ids = scraper.get_active_activity_ids()
        raw_filtered = scraper.get_timesheets(begin=start_date, end=end_date)
        raw_all = scraper.get_timesheets()

        def funnel(entries):
            if entries is None:
                return {'error': 'API nevrátilo data (None)'}
            in_range = billable = matched = 0
            samples = []
            for ts in entries:
                try:
                    bdt = datetime.strptime(ts['begin'], "%Y-%m-%dT%H:%M:%S%z").date()
                except Exception:
                    continue
                aid = ts.get('activity', {}).get('id') if isinstance(ts.get('activity'), dict) else ts.get('activity')
                inr = start_date <= bdt <= end_date
                bil = ts.get('billable') is True
                mat = aid in active_ids
                if inr:
                    in_range += 1
                if bil:
                    billable += 1
                if inr and bil and mat:
                    matched += 1
                if len(samples) < 8:
                    samples.append({'date': str(bdt), 'activity_id': aid,
                                    'billable': ts.get('billable'), 'v_obdobi': inr,
                                    'aktivita_sedi': mat})
            return {'celkem': len(entries), 'v_obdobi': in_range,
                    'billable_true': billable, 'proslo_vsemi_filtry': matched,
                    'ukazky': samples}

        return jsonify({
            'obdobi': {'start': str(start_date), 'end': str(end_date)},
            'aktivni_activity_ids': active_ids,
            'projekt': PROJECT_TITLE,
            's_filtrem_obdobi': funnel(raw_filtered),
            'bez_filtru_obdobi': funnel(raw_all),
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/history', methods=['GET'])
def history():
    """Vrátí historii reportů."""
    limit = request.args.get('limit', 20, type=int)
    return jsonify({'history': get_report_history(limit)})

if __name__ == '__main__':
    seed_config_from_env()

    scheduler = BackgroundScheduler(timezone='Europe/Prague')
    scheduler.add_job(scheduled_check, 'cron', minute='*', id='monthly_report_check')
    scheduler.start()
    print("Scheduler spuštěn — kontroluje odeslání každou minutu.")

    debug = os.getenv('FLASK_DEBUG', 'false').lower() in ('1', 'true', 'yes')
    app.run(debug=debug, host='0.0.0.0', port=5000, use_reloader=False)
