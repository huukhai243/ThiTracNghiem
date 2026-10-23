FROM python:3.13-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    TZ=Asia/Ho_Chi_Minh \
    QUIZ_DATA_DIR=/app/data

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY quiz ./quiz
COPY tests ./tests
COPY run.py wsgi.py ./

EXPOSE 8000
CMD ["python", "run.py", "--port", "8000"]
