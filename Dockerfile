FROM debian:bullseye

USER root

# "psycopg2" will not be installed correctly without 'libpq-dev' and 'build-essential'

RUN apt-get --quiet --assume-yes update && \
    apt-get --no-install-recommends --quiet --assume-yes install \
        python3-pysvn \
        python3-pip \
        python3-dev \
        libpq-dev \
        build-essential \
        libmagic1 \
        curl && \
    python3 -m pip install --upgrade pip && \
    python3 -m pip install --upgrade setuptools wheel

RUN rm -rf /build
COPY --chown=root:root . /build
WORKDIR /build
RUN python3 -m pip install $(pwd) && \
    python3 -m unittest discover -v && \
    python3 setup.py bdist_wheel

HEALTHCHECK --interval=1m --timeout=30s --start-period=15s --retries=3 \
     CMD curl -v --silent http://localhost:5400/clients 2>&1 | grep '< HTTP/1.1 200 OK'

ENTRYPOINT ["python3", "-m", "gunicorn", "oc_client_provider.wsgi:app", "-b", "0.0.0.0:5400"]

