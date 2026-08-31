# Nasazení: Dockge stack + systemd timer

Kontejner je **jednorázová úloha** — spustí `ApiScraperFromKimai.py`, pošle e-mail
a skončí. Cron uvnitř kontejneru je pryč. Plánování řeší systemd timer na hostu,
Dockge slouží jako správa stacku (editace compose souboru, `.env`, ruční build).

## Proč profil `job`

Dockge při „Start" volá `docker compose up -d`. Jednorázová úloha by po doběhnutí
skončila jako `Exited` a stack by v UI svítil červeně. Proto má služba
`profiles: ["job"]` — `up -d` ji vynechá, stack zůstane klidný, a systemd ji
spouští cíleně přes `docker compose --profile job run --rm kimai-report`.

## 0. Odstranit starý cron kontejner

Původní kontejner běžel s `restart: unless-stopped` a cronem uvnitř, takže se sám
nastartuje pokaždé, když naskočí Docker. `docker compose down` ho neodstraní —
nová služba je pod profilem `job`, a `down` sáhne jen na aktivní profily. Smaž ho
ručně, jinak poběží vedle nového řešení a report přijde dvakrát:

```bash
docker rm -f kimai-report
```

## 1. Založit stack v Dockge

Dockge má stacky ve `/opt/stacks/<jméno>` (proměnná `DOCKGE_STACKS_DIR`).
Do stacku patří i zdrojáky, protože compose soubor obsahuje `build: .`:

```bash
sudo git clone <repo> /opt/stacks/kimai-report
cd /opt/stacks/kimai-report
sudo nano .env          # KIMAI_API_TOKEN, SMTP_USER, SMTP_PASS, SMTP_TO
sudo chmod 600 .env
sudo docker compose --profile job build   # první build image
```

Dockge stack po refreshi uvidí (jako neaktivní — to je správně, viz výše).
`.env` můžeš dál editovat přímo v Dockge UI, `env_file: .env` ho načte do kontejneru.

## 2. Nainstalovat unit soubory

```bash
sudo cp systemd/kimai-report.service systemd/kimai-report.timer /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now kimai-report.timer
```

Když stack neleží v `/opt/stacks/kimai-report`, uprav `WorkingDirectory=` v `.service`.

## 3. Ověření

```bash
systemctl list-timers kimai-report.timer   # kdy poběží příště
sudo systemctl start kimai-report.service  # ruční zkušební spuštění
journalctl -u kimai-report.service -f      # log běhu (stdout skriptu)
```

Logy hledej v `journalctl`, ne v Dockge — kontejner se po doběhnutí maže (`--rm`),
takže v UI žádný log nezůstane.

Pro testovací běh bez odeslání na ostrou adresu nastav v `.env`
`SMTP_TO_OVERRIDE=tvuj@mail.cz` — skript pak počítá aktuální měsíc a pošle report tobě.

## Jak to funguje

- `kimai-report.timer` — `OnCalendar=*-*-01 08:00:00`, tj. 1. den v měsíci v 8:00
  místního času serveru. `Persistent=true` znamená, že když byl server v 8:00
  vypnutý, úloha se spustí hned po startu (cron by běh zahodil).
- `kimai-report.service` — `Type=oneshot`, přebuilduje image a spustí
  `docker compose --profile job run --rm kimai-report`. Při chybě to zkusí ještě
  2× po 5 minutách (Kimai server nemusí být hned dostupný).
- Skript končí nenulovým návratovým kódem, když se nepodaří stáhnout data,
  vygenerovat dokument nebo odeslat e-mail — systemd tedy pozná selhání a
  `systemctl status kimai-report` ho ukáže.

## Ruční spuštění

- Z terminálu: `sudo systemctl start kimai-report.service`
- Z Dockge: tlačítko Start stack **nic neudělá** (kvůli profilu). Kdybys chtěl
  spouštět i odtud, smaž řádek `profiles: ["job"]` v `compose.yaml` a z unit
  souboru `--profile job` — pak ale stack v UI po každém běhu zůstane `Exited`.

## Změna času spuštění

Uprav `OnCalendar=` v `kimai-report.timer` a spusť
`sudo systemctl daemon-reload && sudo systemctl restart kimai-report.timer`.
Syntaxi ověříš přes `systemd-analyze calendar '*-*-01 08:00:00'`.

## Notifikace při selhání (volitelné)

Do `[Unit]` v `.service` přidej `OnFailure=status-email@%n.service` a doplň
vlastní notifikační unit.
