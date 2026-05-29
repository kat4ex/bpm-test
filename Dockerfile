FROM mcr.microsoft.com/playwright/python:v1.47.0-jammy

COPY sources.txt /etc/apt/sources.list
RUN rm -f /etc/apt/sources.list.d/*

COPY certs/ /usr/local/share/ca-certificates/
RUN apt-get update && apt-get install -y --no-install-recommends libkrb5-dev \
    && rm -rf /var/lib/apt/lists/* \
    && update-ca-certificates

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .

CMD ["python", "main.py"]