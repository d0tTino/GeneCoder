FROM python:3.11-slim

WORKDIR /workspace

RUN apt-get update && apt-get install -y git && rm -rf /var/lib/apt/lists/*

COPY pyproject.toml poetry.lock ./
RUN pip install --upgrade pip && pip install poetry
RUN poetry install --with gui,web,dev --no-interaction --no-root

COPY . .

CMD ["bash"]
