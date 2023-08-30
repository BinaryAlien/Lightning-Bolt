FROM python:3-alpine

WORKDIR /opt/lightning-bolt
COPY lightning-bolt.py requirements.txt ./

RUN pip3 install -r requirements.txt

ENTRYPOINT ["python3", "./lightning-bolt.py"]
CMD ["/etc/lightning-bolt/groups.json"]
