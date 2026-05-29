FROM mcr.microsoft.com/playwright/python:v1.51.0-jammy

COPY sources.txt /etc/apt/sources.list
RUN rm -f /etc/apt/sources.list.d/* \
    && printf 'Acquire::http::Proxy "DIRECT";\nAcquire::https::Proxy "DIRECT";\n' \
       > /etc/apt/apt.conf.d/00noproxy \
    && printf 'Acquire::http::Proxy "DIRECT";\nAcquire::https::Proxy "DIRECT";\n' \
       > /etc/apt/apt.conf.d/00noproxy

COPY certs/ /usr/local/share/ca-certificates/
RUN apt-get update && apt-get install -y --no-install-recommends libkrb5-dev \
    && rm -rf /var/lib/apt/lists/* \
    && update-ca-certificates

WORKDIR /app
COPY requirements.txt .
ARG PIP_INDEX_URL
ARG PIP_TRUSTED_HOST
RUN pip install --no-cache-dir -r requirements.txt
COPY . .

CMD ["python", "main.py"]