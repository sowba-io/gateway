FROM python:3.8.8-buster

WORKDIR /app

RUN apt-get update && apt-get install -y curl
RUN curl -sSL https://raw.githubusercontent.com/python-poetry/poetry/master/get-poetry.py | python -
ENV PATH="/root/.poetry/bin:$PATH"
RUN poetry config virtualenvs.create false

COPY . /app

RUN make install

CMD ["make", "run-http"]