FROM python:3.11-slim

WORKDIR /app

# Install system dependencies required for compilation and Playwright
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    gcc \
    libffi-dev \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements and install Python packages
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Install Playwright browser (Chromium) and its OS dependencies
# Required by AsyncHtmlLoader for scraping JS-rendered Groww pages
RUN playwright install --with-deps chromium

# Copy application code
COPY . .

# Create directories that may be mapped to Docker volumes
RUN mkdir -p /app/chroma_db /app/data/manifests

EXPOSE 8001

# Default: run the API server. The ingestion service overrides this.
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8001"]
