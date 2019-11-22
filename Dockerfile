FROM python:3

WORKDIR /usr/src/app

COPY requirements.txt ./
RUN pip3 install --no-cache-dir -r requirements.txt
RUN mkdir ~/.aws


COPY snapshot.py .
CMD [ "python", "./snapshot.py", "--exporter", "-p", "default",  "-P", "postgresql-TODAY", "-t", "5" ]
EXPOSE 8080