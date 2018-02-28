FROM python:3-onbuild
COPY . /usr/src/app
CMD ["uwsgi", "--http 0.0.0.0:80 --manage-script-name --mount /=api-osoba-ljudi:app"]
