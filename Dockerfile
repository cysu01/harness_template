FROM python:3.12-slim AS base

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1

RUN apt-get update && apt-get install -y --no-install-recommends \
        git \
        curl \
        ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# Non-root user — sandbox principle: agent should not run as root
RUN useradd --create-home --shell /bin/bash agent
USER agent
WORKDIR /home/agent/app

COPY --chown=agent:agent pyproject.toml README.md ./
COPY --chown=agent:agent src ./src

RUN pip install --user -e ".[redis,vector]"

ENV PATH="/home/agent/.local/bin:${PATH}"

COPY --chown=agent:agent . .

CMD ["python", "-m", "harness.cli"]
