FROM python:3.11-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

RUN mkdir -p products templates

# Railway asigna PORT dinamicamente — no hardcodear
# EXPOSE se usa solo como documentacion
EXPOSE ${PORT:-5000}

CMD ["python", "main.py"]
