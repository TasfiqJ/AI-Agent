FROM python:3.11-slim

RUN pip install --no-cache-dir \
    pytest>=8.0 \
    pytest-cov>=5.0 \
    httpx>=0.27 \
    flask>=3.0 \
    fastapi>=0.115 \
    requests>=2.31

RUN useradd --create-home --uid 1000 sandbox
USER sandbox
WORKDIR /workspace

# Default: run pytest
CMD ["pytest", "-v", "--tb=short"]
