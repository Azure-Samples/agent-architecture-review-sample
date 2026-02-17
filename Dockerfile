# Architecture Review Agent - Hosted Agent for Microsoft Foundry (v2)
# Build: docker build --platform linux/amd64 -t arch-review:v1 .
FROM python:3.12-slim

# Prevent Python from buffering stdout/stderr (important for container logs)
ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1

WORKDIR /app

# Copy everything into user_agent/ sub-directory (foundry-samples convention)
COPY . user_agent/
WORKDIR /app/user_agent

# Install dependencies
RUN if [ -f requirements.txt ]; then \
        pip install --no-cache-dir -r requirements.txt; \
    else \
        echo "No requirements.txt found"; \
    fi

# Run as non-root user for security
RUN useradd --create-home appuser
USER appuser

EXPOSE 8088

CMD ["python", "main.py"]
