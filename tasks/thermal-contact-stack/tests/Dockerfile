FROM python:3.11-slim

RUN pip install --no-cache-dir numpy==2.0.2

WORKDIR /tests
COPY . /tests

CMD ["bash", "/tests/test.sh"]
