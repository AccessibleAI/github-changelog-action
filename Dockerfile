FROM python:3.9-alpine
LABEL "repository"="https://github.com/AccessibleAI/github-changelog-action"
LABEL "homepage"="https://github.com/AccessibleAI/github-changelog-action"
LABEL "maintainer"="Eli Lasry"

WORKDIR /opt

COPY requirements.txt requirements.txt
RUN pip install -r requirements.txt
COPY release_notes.py release_notes.py
ENTRYPOINT ["python"]
CMD ["/opt/release_notes.py"]
