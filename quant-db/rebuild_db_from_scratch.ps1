docker compose down -v

docker rmi quant-db-db:latest

docker compose build --no-cache

docker compose up
