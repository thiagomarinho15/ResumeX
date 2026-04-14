FROM python:3.13-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 8765

CMD ["gunicorn", "run:app", "--bind", "0.0.0.0:8765", "--workers", "2", "--timeout", "180"]
