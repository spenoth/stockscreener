FROM python:3.12-slim

WORKDIR /app

# Optional corporate CA support (set USE_CORP_CA=true when building on corporate network)
ARG USE_CORP_CA=false
COPY zscaler.crt /tmp/zscaler.crt
RUN apt-get update \
 && apt-get install -y --no-install-recommends ca-certificates \
 && if [ "$USE_CORP_CA" = "true" ]; then \
      cp /tmp/zscaler.crt /usr/local/share/ca-certificates/zscaler.crt && update-ca-certificates; \
    fi \
 && rm -rf /var/lib/apt/lists/* /tmp/zscaler.crt

ENV REQUESTS_CA_BUNDLE=/etc/ssl/certs/ca-certificates.crt
ENV SSL_CERT_FILE=/etc/ssl/certs/ca-certificates.crt
ENV CURL_CA_BUNDLE=/etc/ssl/certs/ca-certificates.crt

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Patch certifi only when the corporate CA is enabled
RUN if [ "$USE_CORP_CA" = "true" ]; then \
      cat /usr/local/share/ca-certificates/zscaler.crt \
      >> "$(python -c 'import certifi; print(certifi.where())')"; \
    fi

COPY . .

EXPOSE 8000

CMD ["sh", "-c", "uvicorn main:app --host 0.0.0.0 --port ${API_PORT:-8000}"]
