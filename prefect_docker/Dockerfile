FROM thomasve/prefect_docker_base:latest

ENV PYTHONDONTWRITEBYTECODE 1
ENV PYTHONUNBUFFERED 1

EXPOSE 4200

COPY ./scripts/start-prefect.sh .

RUN apt-get update && apt-get install git -y