FROM mcr.microsoft.com/playwright/python:v1.47.0-jammy

ARG http_proxy
ARG https_proxy
ARG HTTP_PROXY
ARG HTTPS_PROXY
ENV http_proxy="" https_proxy="" HTTP_PROXY="" HTTPS_PROXY=""

COPY certs/ /usr/local/share/ca-certificates/
RUN update-ca-certificates

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .

CMD ["python", "main.py"]