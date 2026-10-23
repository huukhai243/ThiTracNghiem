"""Điểm vào WSGI cho máy chủ web thuê (PythonAnywhere, gunicorn trên VPS...): biến `application` là web Flask.
Chạy trên máy của mình thì dùng `python run.py`."""
from quiz import create_app

application = create_app()
