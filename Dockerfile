FROM python:2.7-buster as py2
COPY requirements*.txt /tmp/
RUN pip install --upgrade --requirement /tmp/requirements-dev.txt && \
    rm --force /tmp/requirements*.txt

FROM python:3.10-buster as py3
COPY requirements*.txt /tmp/
RUN pip install --upgrade --requirement /tmp/requirements-dev.txt && \
    rm --force /tmp/requirements*.txt
