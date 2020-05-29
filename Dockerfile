ARG PYTHON_VERSION=3.7.7
ARG ALPINE_VERSION=3.11
FROM python:${PYTHON_VERSION}-alpine${ALPINE_VERSION}

WORKDIR /src

# Use specific version until this is fixed
# https://github.com/pypa/pipenv/issues/4220
RUN pip install pipenv==2018.11.26

# -- Adding Pipfiles, changes should rebuild whole layer
COPY Pipfile Pipfile
COPY Pipfile.lock Pipfile.lock

# install dependencies from Pipfile.lock for reproducible builds
RUN pipenv install --system --deploy --ignore-pipfile

COPY version_bump.py version_bump.py

ENTRYPOINT ["python", "/src/version_bump.py"]
