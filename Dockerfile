FROM python:3.12-slim
ENV PYTHONUNBUFFERED=1 HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 ENABLE_ML=1
WORKDIR /app
COPY backend/requirements.txt backend/requirements-ml.txt /app/backend/
RUN pip install --no-cache-dir -r backend/requirements.txt -r backend/requirements-ml.txt --extra-index-url https://download.pytorch.org/whl/cpu
COPY backend /app/backend
RUN HF_HUB_OFFLINE=0 TRANSFORMERS_OFFLINE=0 python -m backend.download_model
COPY index.html styles.css legacy.html legacy.css app.js config.js favicon.svg /app/
RUN useradd -m -u 1000 appuser && chown -R appuser:appuser /app
USER appuser
EXPOSE 7860
CMD ["uvicorn", "backend.main:app", "--host", "0.0.0.0", "--port", "7860", "--limit-concurrency", "12", "--timeout-keep-alive", "5"]
