FROM python:3.12-slim
WORKDIR /app
COPY . .
RUN pip install uv && uv sync --all-packages
CMD ["uv", "run", "python", "-m", "chengdu_edu_scheduler.runner"]
