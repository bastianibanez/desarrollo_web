FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /app
COPY services/requirements.txt /app/services/requirements.txt
RUN pip install --no-cache-dir -r services/requirements.txt
COPY services /app/services
CMD ["uvicorn", "services.gateway.gateway:app", "--host", "0.0.0.0", "--port", "8000", "--no-access-log"]
