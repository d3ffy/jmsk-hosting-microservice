FROM python:3.9-slim
WORKDIR /app
COPY ./requirements.txt /app/requirements.txt
RUN apt-get update \
    && apt-get install gcc -y \
    && apt-get clean
RUN pip install -r /app/requirements.txt \
    && rm -rf /root/.cache/pip
EXPOSE 8001
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8001"]