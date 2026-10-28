FROM python:3.12.8-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /app
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt
COPY water_protection ./water_protection
COPY config.example.toml ./config.example.toml
ENTRYPOINT ["python", "-m", "water_protection.cli"]
