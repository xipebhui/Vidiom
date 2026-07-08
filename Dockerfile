FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    VIDIOM_DATABASE_PATH=/data/vidiom.sqlite3

WORKDIR /app

COPY pyproject.toml README.md ./
COPY src ./src

RUN pip install --no-cache-dir .

RUN useradd --create-home --shell /usr/sbin/nologin vidiom \
    && mkdir -p /data \
    && chown -R vidiom:vidiom /data

USER vidiom

VOLUME ["/data"]
EXPOSE 8000
CMD ["vidiom", "serve", "--host", "0.0.0.0", "--port", "8000"]

