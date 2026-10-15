FROM mcr.microsoft.com/playwright/python:v1.40.0-jammy

WORKDIR /app

ENV PYTHONUNBUFFERED=1
ENV TZ=America/Sao_Paulo

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 5050

CMD ["python", "smarttv_web.py", "--host", "0.0.0.0", "--port", "5050"]
