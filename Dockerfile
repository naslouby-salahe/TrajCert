FROM python:3.12-slim

WORKDIR /workspace
COPY requirements.lock pyproject.toml ./
RUN pip install --require-hashes -r requirements.lock
COPY . .
RUN pip install --no-deps .
CMD ["python", "-m", "pytest", "-q"]
