FROM rackspacedot/python38:latest
LABEL maintainer="Mingwei Zhang <mingwei@caida.org>"

WORKDIR /src
COPY setup.py .
COPY collector collector/
RUN python3 -m pip install .

CMD roa-collector -h
