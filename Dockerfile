FROM python:3.12-slim

WORKDIR /app

COPY requirements.txt pyproject.toml README.md ./
COPY src ./src
RUN pip install --no-cache-dir -r requirements.txt \
    && pip install --no-cache-dir --no-deps .

# Data files are Git LFS-tracked and large, so they are not baked into the
# image -- mount them (and an output dir) at runtime:
#   docker run --rm --env-file .env \
#     -v "$PWD/data:/app/data" -v "$PWD/output:/app/output" \
#     kasa-report "why is AMAZON doing bad in month 5 2026"
ENV KASA_DATA_DIR=/app/data \
    KASA_OUTPUT_DIR=/app/output

ENTRYPOINT ["kasa-report"]
