FROM registry.ci.data.com/mobileidentity/python:3.6

LABEL authors="Mobile Identity <mobileidentity@salesforce.com>"

ADD . /lib
WORKDIR /lib

RUN pip install -r requirements.txt -r requirements-dev.txt
