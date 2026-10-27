FROM python:3.12-slim

ARG INSTALL_FINBERT=false

WORKDIR /app

COPY requirements.txt requirements-dev.txt requirements-sentiment.txt ./
RUN pip install --no-cache-dir -r requirements.txt \
    && useradd --create-home --uid 10001 appuser

RUN if [ "$INSTALL_FINBERT" = "true" ]; then \
        pip install --no-cache-dir torch --index-url https://download.pytorch.org/whl/cpu \
        && pip install --no-cache-dir -r requirements-sentiment.txt; \
    fi

COPY . .

USER appuser

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
