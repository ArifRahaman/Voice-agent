# Container image for hosting the voice agent worker (LiveKit Cloud, Render, a VPS, etc.).
# On a server, run it with HOSTED=1 so the computer-control tools switch off and only the
# cloud-safe tools (web_search, get_current_time) stay on. See src/agent.py.
FROM python:3.12-slim

# Keep Python output unbuffered so logs show up live, and don't write .pyc files.
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    HOSTED=1

WORKDIR /app

# Install dependencies first so Docker caches this layer when only source changes.
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

# Copy the agent source.
COPY src ./src

# Download the model files the plugins need (e.g. Silero VAD) at build time, so the
# first call isn't slowed down fetching them.
RUN python src/agent.py download-files || true

# LiveKit workers connect out to LiveKit Cloud; they don't accept inbound traffic, so no
# port is exposed. `start` is the production run mode (vs `dev`, which hot-reloads).
CMD ["python", "src/agent.py", "start"]
