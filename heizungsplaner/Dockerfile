ARG BUILD_FROM=ghcr.io/home-assistant/amd64-base:3.19
FROM $BUILD_FROM

RUN apk add --no-cache python3 py3-pip

COPY backend/requirements.txt /tmp/requirements.txt
RUN pip3 install --no-cache-dir --break-system-packages -r /tmp/requirements.txt

# Auch die config.yaml wandert ins Abbild: Aus ihr liest die Oberfläche
# ihre Fassungsnummer, damit sie nicht an zwei Stellen gepflegt werden muss.
COPY config.yaml /app/config.yaml
COPY backend /app/backend
COPY frontend /app/frontend
COPY run.sh /run.sh
RUN chmod +x /run.sh

CMD [ "/run.sh" ]
