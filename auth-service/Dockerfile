FROM python:3.11-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY ./app ./app
COPY ./init_db.py ./init_db.py
COPY ./wsgi.py ./wsgi.py
COPY ./app/private_key.pem ./app/private_key.pem
COPY ./app/public_key.pem ./app/public_key.pem
ENV FLASK_ENV=production
ENV PYTHONUNBUFFERED=1
RUN mkdir -p /app/db_data && \
    useradd -u 8888 appuser && \
    chown -R appuser:appuser /app /app/db_data
USER appuser
EXPOSE 5000
CMD ["sh", "-c", "python init_db.py && gunicorn --bind 0.0.0.0:5000 --workers 2 --threads 4 wsgi:app"]