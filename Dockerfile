FROM node:22-bookworm-slim

# Install Python, git, and system deps
RUN apt-get update && apt-get install -y \
    python3 python3-pip python3-venv git curl \
    && rm -rf /var/lib/apt/lists/*

# Install Claude Code CLI globally
RUN npm install -g @anthropic-ai/claude-code

# Set up app directory
WORKDIR /app

# Copy and install Python deps
COPY pyproject.toml ./
COPY dream_team/ ./dream_team/
COPY dream.py ./

RUN pip3 install --break-system-packages -e . && \
    pip3 install --break-system-packages fastapi uvicorn python-multipart

# Create data directories
RUN mkdir -p /root/.dream-team/projects

# Expose port
EXPOSE 8000

# Environment
ENV PYTHONUNBUFFERED=1

# Launch web server
CMD ["python3", "-m", "dream_team.web.run", "--host", "0.0.0.0", "--port", "8000"]
