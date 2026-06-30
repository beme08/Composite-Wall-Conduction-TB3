FROM python:3.11-slim AS builder

RUN apt-get update \
    && apt-get install -y --no-install-recommends gcc libc6-dev \
    && rm -rf /var/lib/apt/lists/*
COPY private_oracle.c /tmp/private_oracle.c
RUN cc -O2 -s -DHORIZON_LIMIT=2.0 /tmp/private_oracle.c -lm -o /tmp/sysid_probe_core \
    && cc -O2 -s -DHORIZON_LIMIT=6.0 /tmp/private_oracle.c -lm -o /tmp/sysid_truth_core

FROM python:3.11-slim

RUN pip install --no-cache-dir numpy==2.0.2 scipy==1.14.1
COPY --from=builder /tmp/sysid_probe_core /usr/local/lib/sysid_probe_core
COPY --from=builder /tmp/sysid_truth_core /usr/local/lib/sysid_truth_core
RUN chmod 0555 /usr/local/lib/sysid_probe_core \
    && chmod 0500 /usr/local/lib/sysid_truth_core

WORKDIR /tests
COPY test.sh test_sysid.py /tests/
CMD ["bash", "/tests/test.sh"]
