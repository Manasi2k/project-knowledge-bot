FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1 PIP_NO_CACHE_DIR=1 \
    PYTHONPATH=/app STREAMLIT_BROWSER_GATHER_USAGE_STATS=false

RUN apt-get update \
    && apt-get install -y --no-install-recommends tesseract-ocr tesseract-ocr-eng \
    && rm -rf /var/lib/apt/lists/*

RUN useradd -m app && mkdir -p /app /data && chown app:app /data

WORKDIR /app
COPY requirements.txt .
# CPU-only PyTorch (the default Linux build is several GB larger), then everything else
RUN pip install torch --index-url https://download.pytorch.org/whl/cpu \
    && grep -viE '^(torch|nvidia-|triton)' requirements.txt > requirements.docker.txt \
    && pip install -r requirements.docker.txt

COPY . /app
USER app
# download the embedding model once, at build time
RUN python -c "from sentence_transformers import SentenceTransformer; SentenceTransformer('sentence-transformers/all-MiniLM-L6-v2')"

WORKDIR /data
EXPOSE 8501
CMD ["python", "-m", "streamlit", "run", "/app/app.py", "--server.address=0.0.0.0", "--server.port=8501", "--server.headless=true"]