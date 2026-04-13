#------------------------------------------------------------------------------
# Docker-Image: decisionmap/ai-service
#
# Build:
#   ./docker/build.sh --build
#
# Run:
#   docker run --rm -p 8000:8000 \
#       -e POSTGRES_URL="postgresql://user:pass@host:5432/db" \
#       -e OPENAI_API_KEY="sk-..." \
#       decisionmap/ai-service
#------------------------------------------------------------------------------

FROM python:3.11-slim AS builder

LABEL org.opencontainers.image.authors="Mike Mitterer <office@mikemitterer.at>"

RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    g++ \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir --user -r requirements.txt

FROM python:3.11-slim AS runner

RUN DEBIAN_FRONTEND=noninteractive apt-get update && apt-get install -y --no-install-recommends \
    mc \
    jq \
    && rm -rf /var/lib/apt/lists/*

ENV TERM=xterm-256color

WORKDIR /app
COPY --from=builder /root/.local /opt/.local
COPY . .
ENV PATH=/opt/.local/bin:$PATH
ENV PYTHONPATH=/opt/.local/lib/python3.11/site-packages

RUN useradd -m -u 1000 appuser \
    && chown -R appuser:appuser /app /opt/.local
USER appuser

EXPOSE 8000
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
