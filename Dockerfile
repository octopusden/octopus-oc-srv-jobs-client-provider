FROM python:3.12-slim AS builder

RUN apt-get update && \
    apt-get install -y --no-install-recommends \
        python3-svn \
        python3-dev \
        libpq-dev \
        build-essential \
        libmagic1 \
        curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /build

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# TODO: implement coverage report and need to cover > 90% testccse
RUN coverage run -m pytest

FROM python:3.12-slim

WORKDIR /local

RUN apt-get update && \
    apt-get install -y --no-install-recommends \
        libpq5 \
        libmagic1 \
        curl \
    && rm -rf /var/lib/apt/lists/*

COPY --from=builder /usr/local/lib/python3.12/site-packages /usr/local/lib/python3.12/site-packages
COPY --from=builder /usr/local/bin /usr/local/bin

COPY . .

HEALTHCHECK --interval=1m --timeout=30s --start-period=15s --retries=3 \
    CMD curl -f http://localhost:5400/clients || exit 1

ENTRYPOINT ["gunicorn", "oc_client_provider.wsgi:app", "-b", "0.0.0.0:5400"]