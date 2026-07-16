# adjust to version on relevant machines, or dictate it before then
FROM python:3.14.5 

WORKDIR /venus

COPY controller.py .
COPY watcher.py .

# default command that is overriden by profiles
CMD python controller.py
