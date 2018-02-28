#!/bin/bash


echo "Gasim uwsgi";

pkill -f api-osoba-ljudi

sleep 1

echo "Pokrecem uwsgi na portu 8080";

uwsgi --http 0.0.0.0:8080 --manage-script-name --mount /=api-osoba-ljudi:app & 
