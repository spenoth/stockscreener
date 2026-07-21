FROM python:3.12-slim

WORKDIR /app

# Install Zscaler corporate CA into the OS trust store
COPY zscaler.crt /usr/local/share/ca-certificates/zscaler.crt
RUN apt-get update \
 && apt-get install -y --no-install-recommends ca-certificates \
 && update-ca-certificates \
 && rm -rf /var/lib/apt/lists/*

ENV REQUESTS_CA_BUNDLE=/etc/ssl/certs/ca-certificates.crt
ENV SSL_CERT_FILE=/etc/ssl/certs/ca-certificates.crt
ENV CURL_CA_BUNDLE=/etc/ssl/certs/ca-certificates.crt

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Append Zscaler cert to the certifi bundle that the Alpaca SDK uses directly
RUN cat /usr/local/share/ca-certificates/zscaler.crt \
    >> "$(python -c 'import certifi; print(certifi.where())')"

COPY . .

EXPOSE 8000

CMD ["sh", "-c", "uvicorn main:app --host 0.0.0.0 --port ${API_PORT:-8000}"]
