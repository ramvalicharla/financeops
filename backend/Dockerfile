FROM python:3.11-slim AS runtime

WORKDIR /app

RUN apt-get update && apt-get install -y \
    gcc libpq-dev curl \
    libgobject-2.0-0 \
    libpango-1.0-0 \
    libpangocairo-1.0-0 \
    libcairo2 \
    libffi-dev \
    shared-mime-info \
    fonts-liberation \
    fonts-dejavu-core \
    && rm -rf /var/lib/apt/lists/*

COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

# Install venv to /opt/venv so it survives the host-dir volume mount on /app
RUN python -m venv /opt/venv
ENV UV_PROJECT_ENVIRONMENT=/opt/venv
ENV PATH="/opt/venv/bin:$PATH"
RUN echo "build-breaker-$(date)"
RUN pip install --no-cache-dir psycopg2-binary==2.9.10
RUN python -c "import psycopg2; print('psycopg2 preinstall OK')"

COPY pyproject.toml uv.lock ./
RUN uv sync --locked --no-dev
RUN python -c "import importlib.util as _u; m=_u.find_spec('weasyprint'); \
print('WeasyPrint not installed; skipping smoke check' if m is None else 'WeasyPrint package detected')" \
    && python -c "import importlib.util as _u; \
import sys; \
m=_u.find_spec('weasyprint'); \
sys.exit(0 if m is None else 42)" \
    || python -c "import weasyprint; weasyprint.HTML(string='<p>ok</p>').write_pdf(); print('WeasyPrint OK')"

COPY . ./
COPY scripts/start.sh /app/scripts/start.sh
RUN chmod +x /app/scripts/start.sh

RUN groupadd -g 1000 financeops \
    && useradd -g financeops -u 1000 -d /app -s /sbin/nologin financeops \
    && mkdir -p /app/.cache \
    && chown -R financeops:financeops /app

ENV HOME=/app

USER financeops
ENV CLAMAV_REQUIRED=True

EXPOSE 8000

CMD uvicorn financeops.main:app --host 0.0.0.0 --port ${PORT:-8000}

FROM runtime AS production
