FROM python:3.9.2

WORKDIR /app/
ADD requirements.txt .
RUN pip install -r requirements.txt

ADD . .

CMD ["python3", "run.py"]
