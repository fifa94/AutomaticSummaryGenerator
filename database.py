import sqlite3
import json
from datetime import datetime
from pathlib import Path

DB_PATH = Path('report_config.db')

def init_db():
    """Inicializuje databázi."""
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()

    c.execute('''CREATE TABLE IF NOT EXISTS config (
        id INTEGER PRIMARY KEY,
        schedule_day INTEGER DEFAULT 1,
        schedule_time TEXT DEFAULT '08:00',
        recipients TEXT DEFAULT '',
        enabled INTEGER DEFAULT 1,
        hourly_rate REAL DEFAULT 350,
        updated_at TIMESTAMP
    )''')

    c.execute('''CREATE TABLE IF NOT EXISTS report_history (
        id INTEGER PRIMARY KEY,
        sent_date TIMESTAMP,
        recipients TEXT,
        status TEXT,
        file_name TEXT,
        error_message TEXT
    )''')

    # Ujistíme se, že sloupec hourly_rate existuje
    try:
        c.execute('ALTER TABLE config ADD COLUMN hourly_rate REAL DEFAULT 350')
    except sqlite3.OperationalError:
        pass  # Sloupec už existuje

    conn.commit()
    conn.close()

def get_config():
    """Vrátí aktuální konfiguraci."""
    init_db()
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('SELECT schedule_day, schedule_time, recipients, enabled, hourly_rate FROM config LIMIT 1')
    result = c.fetchone()
    conn.close()

    if result:
        return {
            'schedule_day': result[0],
            'schedule_time': result[1],
            'recipients': result[2].split(';') if result[2] else [],
            'enabled': bool(result[3]),
            'hourly_rate': result[4] if result[4] else 350
        }
    return {
        'schedule_day': 1,
        'schedule_time': '08:00',
        'recipients': [],
        'enabled': True,
        'hourly_rate': 350
    }

def save_config(schedule_day, schedule_time, recipients, enabled, hourly_rate=350):
    """Uloží konfiguraci."""
    init_db()
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()

    recipients_str = ';'.join(recipients) if recipients else ''

    c.execute('DELETE FROM config')
    c.execute('''INSERT INTO config (schedule_day, schedule_time, recipients, enabled, hourly_rate, updated_at)
                 VALUES (?, ?, ?, ?, ?, ?)''',
              (schedule_day, schedule_time, recipients_str, int(enabled), hourly_rate, datetime.now()))

    conn.commit()
    conn.close()

def add_report_history(recipients, status, file_name=None, error_message=None):
    """Přidá záznam do historie."""
    init_db()
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()

    recipients_str = ';'.join(recipients) if recipients else ''

    c.execute('''INSERT INTO report_history (sent_date, recipients, status, file_name, error_message)
                 VALUES (?, ?, ?, ?, ?)''',
              (datetime.now(), recipients_str, status, file_name, error_message))

    conn.commit()
    conn.close()

def get_report_history(limit=20):
    """Vrátí historii odeslaných reportů."""
    init_db()
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('''SELECT id, sent_date, recipients, status, file_name, error_message
                 FROM report_history
                 ORDER BY sent_date DESC
                 LIMIT ?''', (limit,))
    results = c.fetchall()
    conn.close()

    history = []
    for row in results:
        history.append({
            'id': row[0],
            'sent_date': row[1],
            'recipients': row[2].split(';') if row[2] else [],
            'status': row[3],
            'file_name': row[4],
            'error_message': row[5]
        })

    return history
