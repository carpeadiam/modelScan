# Used ONLY by `gcloud run deploy --source .` for the dashboard.
FROM python:3.11-slim
ENV PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1
WORKDIR /srv
COPY requirements-ml.txt requirements-web.txt ./
RUN pip install -r requirements-web.txt
COPY app ./app
COPY ml ./ml
COPY pg ./pg
COPY run.py gunicorn.conf.py ./
RUN useradd -m appuser && chown -R appuser /srv
USER appuser
ENV PG_USE_GCP=true
CMD ["gunicorn", "-c", "gunicorn.conf.py", "run:app"]
