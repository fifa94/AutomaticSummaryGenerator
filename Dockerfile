FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Instalace cronu
RUN apt-get update && apt-get install -y cron && rm -rf /var/lib/apt/lists/*

COPY . .

# Nastavení crontabu a práv
COPY crontab /etc/cron.d/kimai-report
RUN chmod 0644 /etc/cron.d/kimai-report

# Složka pro výstupní dokumenty (mount volume sem)
RUN mkdir -p /app/output

# Log soubor pro cron
RUN touch /var/log/kimai.log

RUN chmod +x entrypoint.sh

# Proměnné se předávají za běhu: docker run --env-file .env ...
ENV KIMAI_API_TOKEN=""
ENV KIMAI_API_URL=""
ENV SMTP_USER=""
ENV SMTP_PASS=""
ENV SMTP_TO=""
ENV OUTPUT_DIR="/app/output"

ENTRYPOINT ["./entrypoint.sh"]
