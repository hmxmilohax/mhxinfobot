FROM python:3.12-slim

WORKDIR /app

RUN pip install --no-cache-dir -U discord.py requests

COPY . .
COPY docker-entrypoint.sh /docker-entrypoint.sh
RUN chmod +x /docker-entrypoint.sh

ENTRYPOINT ["/docker-entrypoint.sh"]
