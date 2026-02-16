# Architecture Review Agent — Hosted Agent for Microsoft Foundry
# Build: docker build --platform linux/amd64 -t arch-review:v1 .
FROM python:3.12-slim

# Prevent Python from buffering stdout/stderr (important for container logs)
ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1

WORKDIR /app

# Install dependencies first for better Docker layer caching
COPY requirements.txt user_agent/requirements.txt
RUN pip install --no-cache-dir -r user_agent/requirements.txt

# Copy everything into user_agent/ sub-directory (foundry-samples convention)
COPY . user_agent/
WORKDIR /app/user_agent

# Run as non-root user for security
RUN useradd --create-home appuser
USER appuser

EXPOSE 8088

HEALTHCHECK --interval=30s --timeout=5s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8088/')" || exit 1

CMD ["python", "main.py"]
