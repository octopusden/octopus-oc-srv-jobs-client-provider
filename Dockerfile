ARG PYTHON_VERSION=3.7
FROM python:${PYTHON_VERSION}

USER root
RUN apt-get --quiet --assume-yes update && apt-get --quiet --assume-yes install sqlite3 curl
RUN rm -rf /build
COPY --chown=root:root . /build
WORKDIR /build
RUN python -m pip install $(pwd) && python -m unittest discover -v && python setup.py bdist_wheel

HEALTHCHECK --interval=1m --timeout=30s --start-period=15s --retries=3 \
     CMD curl -v --silent http://localhost:5400/clients 2>&1 | grep '< HTTP/1.1 200 OK'

ENTRYPOINT ["python", "-m", "gunicorn", "oc_client_provider.wsgi:app", "-b", "0.0.0.0:5400"]

