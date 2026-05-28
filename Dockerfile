FROM mcr.microsoft.com/playwright/python:v1.51.0-jammy

COPY certs/ /usr/local/share/ca-certificates/
RUN update-ca-certificates

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .

CMD ["python", "main.py"]