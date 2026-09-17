FROM python:3.11.14-slim-bookworm@sha256:65a93d69fa75478d554f4ad27c85c1e69fa184956261b4301ebaf6dbb0a3543d
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PIP_DISABLE_PIP_VERSION_CHECK=1
WORKDIR /app
COPY tools/campus/requirements.lock /tmp/deps/requirements.lock
RUN pip install --no-cache-dir -r /tmp/deps/requirements.lock
COPY backend /app
RUN mkdir -p /app/logs /runtime/attachments
ENTRYPOINT ["python", "campus_bootstrap.py"]
