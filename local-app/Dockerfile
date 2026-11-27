FROM python:3.12-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt \
    && useradd --create-home --uid 10001 app

COPY server.py index.html ./

USER app

ENV HOST=0.0.0.0
ENV PORT=8766

EXPOSE 8766

CMD ["python", "server.py"]
