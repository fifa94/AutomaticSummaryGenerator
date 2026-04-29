#!/bin/bash
# Cron nezdědí env proměnné z Dockeru — exportujeme je do /etc/environment
printenv | grep -v "no_proxy" >> /etc/environment

# Spustíme cron v popředí (jinak by kontejner okamžitě skončil)
exec cron -f
