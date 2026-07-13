docker compose down -v

docker rmi quant-db-api:latest

docker compose build --no-cache

docker compose up
