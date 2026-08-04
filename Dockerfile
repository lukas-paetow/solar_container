# adjust to version on relevant machines, or dictate it before then
FROM python:3.14.5 

RUN python -m pip install kubernetes

WORKDIR /venus

COPY controller.py .

CMD python controller.py
