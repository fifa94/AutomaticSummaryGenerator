FROM python:3.11-slim

WORKDIR /app

# Časová zóna kvůli výpočtu měsíce v reportu (jinak kontejner běží v UTC)
ENV TZ=Europe/Prague
RUN apt-get update && apt-get install -y --no-install-recommends tzdata \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Složka pro výstupní dokumenty (mount volume sem)
RUN mkdir -p /app/output

# Logy jdou rovnou na stdout -> zachytí je journald na hostu
ENV PYTHONUNBUFFERED=1

# Proměnné se předávají za běhu: docker run --env-file .env ...
ENV KIMAI_API_TOKEN=""
ENV KIMAI_API_URL=""
ENV SMTP_USER=""
ENV SMTP_PASS=""
ENV SMTP_TO=""
ENV OUTPUT_DIR="/app/output"

# Kontejner je jednorázová úloha: doběhne a skončí.
# Plánování řeší systemd timer na hostu (viz systemd/).
CMD ["python", "ApiScraperFromKimai.py"]
