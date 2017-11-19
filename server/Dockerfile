FROM python:3.6
COPY requirements.txt /usr/src/
RUN pip install --upgrade pip && \
    pip install --no-cache-dir -r /usr/src/requirements.txt
WORKDIR /usr/src/app
EXPOSE 5000
ENTRYPOINT ["python", "api.py"]
COPY . /usr/src/app
