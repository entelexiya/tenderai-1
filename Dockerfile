FROM python:3.12-slim
ENV PYTHONUNBUFFERED=1 ENABLE_ML=0
WORKDIR /app
COPY backend/requirements.txt /app/backend/
RUN pip install --no-cache-dir -r backend/requirements.txt
COPY backend /app/backend
COPY index.html styles.css legacy.html legacy.css app.js config.js favicon.svg /app/
RUN useradd -m -u 1000 appuser && chown -R appuser:appuser /app
USER appuser
EXPOSE 7860
CMD ["uvicorn", "backend.main:app", "--host", "0.0.0.0", "--port", "7860", "--limit-concurrency", "12", "--timeout-keep-alive", "5"]
