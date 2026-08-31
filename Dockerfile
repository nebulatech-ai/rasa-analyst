FROM python:3.13-slim

WORKDIR /app
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    RASA_ENV=production \
    RASA_HOST=0.0.0.0 \
    RASA_PORT=8787 \
    RASA_ALLOWED_HOSTS=* \
    OLLAMA_HOST=http://host.docker.internal:11434

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY engine ./engine
COPY static ./static
COPY app.py run.py settings.py ./

EXPOSE 8787
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8787/api/health')"

CMD ["python", "run.py"]
