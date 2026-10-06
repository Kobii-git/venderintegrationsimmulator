FROM python:3.12-slim
RUN apt-get update \
    && apt-get install -y --no-install-recommends openssl \
    && rm -rf /var/lib/apt/lists/* \
    && mkdir -p /certs \
    && openssl req -x509 -newkey rsa:2048 -nodes -days 2 \
       -subj "/CN=receiver" \
       -keyout /certs/server.key -out /certs/server.crt
COPY receiver.py /receiver.py
CMD ["python", "/receiver.py"]
