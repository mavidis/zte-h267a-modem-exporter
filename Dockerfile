FROM python:3.11-slim

WORKDIR /app

# Create non-root user
RUN useradd -u 1000 -m -s /bin/bash appuser

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY exporter/ ./exporter/

RUN chown -R appuser:appuser /app

USER appuser

EXPOSE 9877

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:9877/metrics')" || exit 1

CMD ["python", "-u", "exporter/app.py"]
