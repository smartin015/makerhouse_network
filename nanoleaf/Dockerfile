FROM python:3

RUN apt update && apt -y install python3-pip && pip3 install nanoleafapi paho-mqtt && rm -rf /var/lib/apt/lists*

COPY main.py /

CMD python3 main.py
