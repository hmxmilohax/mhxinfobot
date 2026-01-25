FROM python:3.12-slim

WORKDIR /opt

# git is needed so we can pull on container start
RUN apt-get update && apt-get install -y --no-install-recommends \
    git ca-certificates \
  && rm -rf /var/lib/apt/lists/*

# deps used by the bot (repo README mentions discord.py; code uses requests)
RUN pip install --no-cache-dir -U discord.py requests

COPY entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

ENV REPO_URL="https://github.com/hmxmilohax/mhxinfobot"
ENV APP_DIR="/opt/mhxinfobot"

ENTRYPOINT ["/entrypoint.sh"]
