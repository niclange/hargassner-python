FROM python:3

COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt
COPY hargdata.py ./
COPY hargMqtt.py ./

CMD [ "python", "./hargMqtt.py" ]