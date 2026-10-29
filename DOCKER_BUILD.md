# Docker Build & Push Instructions

## Prerequisites
1. Docker Desktop musí běžet
2. Být přihlášený v Docker Hub: `docker login`

## Build image
```bash
docker build -t fifa94/automatic-summary-generator:latest .
```

## Test image lokálně
```bash
docker run -p 5000:5000 --env-file .env fifa94/automatic-summary-generator:latest
```

## Push do Docker Hub
```bash
docker push fifa94/automatic-summary-generator:latest
```

## Tagging (optional)
```bash
docker tag fifa94/automatic-summary-generator:latest fifa94/automatic-summary-generator:v1.0
docker push fifa94/automatic-summary-generator:v1.0
```

## Run from Docker Hub
```bash
docker run -p 5000:5000 --env-file .env fifa94/automatic-summary-generator:latest
```
