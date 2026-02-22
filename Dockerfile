FROM python:3.12-slim

# System dependencies for PyMuPDF, Tesseract, etc.
RUN apt-get update && apt-get install -y --no-install-recommends \
    tesseract-ocr \
    tesseract-ocr-eng \
    libgl1 \
    libglib2.0-0 \
    curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install Python dependencies
COPY pyproject.toml ./
RUN pip install --no-cache-dir -e ".[dev]" 2>/dev/null || pip install --no-cache-dir .

# Download spaCy model
RUN python -m spacy download en_core_web_sm

# Copy application code
COPY src/ src/
COPY tests/ tests/

# Create data directories
RUN mkdir -p data/raw data/processed data/thumbnails

EXPOSE 8000

# Default: run web server
CMD ["uvicorn", "src.main:app", "--host", "0.0.0.0", "--port", "8000"]
