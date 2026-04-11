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

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir --user -r requirements.txt

FROM python:3.11-slim AS runner

# - System-Tools --------------------------------------------------------------
RUN DEBIAN_FRONTEND=noninteractive apt-get clean && apt-get -y update && apt-get install -y \
    mc \
    jq \
    && apt-get autoremove -y \
    && rm -rf /var/lib/apt/lists/*

ENV TERM=xterm-256color

WORKDIR /app
COPY --from=builder /root/.local /root/.local
COPY . .
ENV PATH=/root/.local/bin:$PATH

RUN useradd -m -u 1000 appuser && chown -R appuser:appuser /app
USER appuser

EXPOSE 8000
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
