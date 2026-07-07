# Minimal image for the API / dashboard (docs/DEPLOYMENT.md §2).
# The HMAC secret is provided at runtime via the environment — never in the image.
FROM python:3.11-slim

WORKDIR /app

# psycopg (binary) for PostgreSQL on server/cloud profiles.
COPY pyproject.toml README.md ./
COPY src ./src
RUN pip install --no-cache-dir -e ".[dashboard]" "psycopg[binary]>=3.1"

COPY apps ./apps
COPY scripts ./scripts

EXPOSE 8000 8501
CMD ["uvicorn", "apps.api.main:app", "--host", "0.0.0.0", "--port", "8000"]
