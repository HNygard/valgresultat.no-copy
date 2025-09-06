FROM python:3.11-slim

# Create a user with your host UID
ARG UID=1000
ARG GID=1000
RUN groupadd -g ${GID} appgroup && \
    useradd -m -u ${UID} -g appgroup appuser

USER appuser

WORKDIR /app

# Install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY src/ .

CMD ["python", "monitor.py"]
