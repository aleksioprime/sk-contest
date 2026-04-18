FROM python:3.12.11-slim-bullseye

WORKDIR /usr/src/app

ENV PYTHONPATH=/usr/src/app:$PYTHONPATH
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV TZ=Europe/Moscow

RUN apt-get update && apt-get install -y tzdata && rm -rf /var/lib/apt/lists/*
RUN ln -snf /usr/share/zoneinfo/$TZ /etc/localtime && echo $TZ > /etc/timezone

COPY ./requirements.txt ./
RUN pip install --upgrade pip && pip install -r requirements.txt

COPY . .
RUN chmod +x /usr/src/app/entrypoint.sh

ENTRYPOINT ["/usr/src/app/entrypoint.sh"]
