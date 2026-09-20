FROM python:3.11-alpine

WORKDIR /app

COPY app.py /app/app.py

RUN chmod +x /app/app.py

EXPOSE 9878

CMD ["python", "-u", "/app/app.py"]
