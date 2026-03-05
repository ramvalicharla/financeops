FROM python:3.12-slim

WORKDIR /app

RUN apt-get update && apt-get install -y \
    gcc libpq-dev curl \
    && rm -rf /var/lib/apt/lists/*

COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

# Install venv to /opt/venv so it survives the host-dir volume mount on /app
ENV UV_PROJECT_ENVIRONMENT=/opt/venv
ENV PATH="/opt/venv/bin:$PATH"

COPY pyproject.toml .
RUN uv sync --no-dev

COPY . .

EXPOSE 8000

CMD ["uvicorn", "financeops.main:app", "--host", "0.0.0.0", "--port", "8000"]
