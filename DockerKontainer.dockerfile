# Použijeme oficiální Python image
FROM python:3.11-slim

# Nastavíme pracovní adresář v kontejneru
WORKDIR /app

# Zkopírujeme requirements.txt (budeme ho vytvářet níže)
COPY requirements.txt .

# Nainstalujeme potřebné balíčky
RUN pip install --no-cache-dir -r requirements.txt

# Zkopírujeme celý projekt do kontejneru
COPY . .

# Nastavíme environment proměnné (doporučeno pro bezpečnost)
ENV SMTP_USER=""
ENV SMTP_PASS=""
ENV BEARER_TOKEN=""

# Spustíme Python skript
CMD ["python", "ApiScraperFromKimai.py"]