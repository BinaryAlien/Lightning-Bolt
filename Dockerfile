FROM python:3-alpine

COPY requirements.txt .
RUN pip3 install -r requirements.txt

WORKDIR /opt/lightning-bolt
COPY lightning-bolt.py .

ENTRYPOINT ["python3", "./lightning-bolt.py"]
CMD ["/etc/lightning-bolt/groups.yml"]
