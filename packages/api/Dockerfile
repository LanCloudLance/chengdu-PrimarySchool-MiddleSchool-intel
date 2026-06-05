FROM python:3.12-slim
WORKDIR /app
COPY . .
RUN pip install uv && uv sync --all-packages
RUN chmod +x scripts/docker-entrypoint-api.sh
ENTRYPOINT ["scripts/docker-entrypoint-api.sh"]
