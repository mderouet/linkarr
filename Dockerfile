FROM python:3.12-alpine

RUN pip install --no-cache-dir \
    "guessit>=3.8,<4" \
    "aniparse>=1.2,<2"

WORKDIR /app

COPY organize.py entrypoint.sh ./
RUN chmod +x entrypoint.sh

VOLUME /data

ENTRYPOINT ["./entrypoint.sh"]
