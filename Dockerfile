FROM python:3.11-slim

WORKDIR /app

COPY pyproject.toml .
COPY src ./src

RUN pip install --no-cache-dir .

RUN useradd -m appuser
USER appuser

EXPOSE 8000

CMD ["ahq-mcp-http"]
