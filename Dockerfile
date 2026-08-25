FROM python:3.13.15-slim-bookworm

WORKDIR /workspace
COPY requirements.lock pyproject.toml ./
RUN python -m pip install --only-binary=:all: --require-hashes -r requirements.lock
COPY src ./src
COPY tests ./tests
COPY configs ./configs
RUN pip install --no-deps . && \
    groupadd --system trajcert && \
    useradd --system --gid trajcert --home-dir /nonexistent --no-create-home trajcert && \
    chown -R trajcert:trajcert /workspace
USER trajcert
CMD ["trajcert", "doctor"]
