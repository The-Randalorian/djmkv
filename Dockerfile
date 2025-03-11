FROM ubuntu:24.04
LABEL authors="The_Randalorian"
SHELL ["bash", "-c"]
RUN apt-get update && apt-get upgrade -y

# TODO: Setup a two stage build. This will make the final image smaller.

ARG MAKEMKV_VERSION="1.17.9"
WORKDIR /makemkv
RUN apt-get install -y build-essential pkg-config libc6-dev libssl-dev libexpat1-dev libavcodec-dev libgl1-mesa-dev qtbase5-dev zlib1g-dev wget default-jre curl ccextractor
RUN wget "https://www.makemkv.com/download/makemkv-bin-$MAKEMKV_VERSION.tar.gz" https://www.makemkv.com/download/makemkv-oss-$MAKEMKV_VERSION.tar.gz
RUN tar -xzf "makemkv-bin-$MAKEMKV_VERSION.tar.gz"
RUN tar -xzf "makemkv-oss-$MAKEMKV_VERSION.tar.gz"
RUN rm "makemkv-bin-$MAKEMKV_VERSION.tar.gz" "makemkv-oss-$MAKEMKV_VERSION.tar.gz"
WORKDIR /makemkv/makemkv-oss-$MAKEMKV_VERSION
RUN ./configure && make && make install
WORKDIR /makemkv/makemkv-bin-$MAKEMKV_VERSION
ARG MAKEMKV_ACCEPT_EULA
RUN test -n "$MAKEMKV_ACCEPT_EULA" || exit 2  # You must accept the MakeMKV eula. Set MAKEMKV_ACCEPT_EULA to anything to accept
RUN mkdir tmp && echo accepted > tmp/eula_accepted
RUN make && make install
ARG MAKEMKV_KEY
RUN test -z "$MAKEMKV_KEY" || makemkvcon -r reg $MAKEMKV_KEY
RUN makemkvcon -r info dev:/dev/null  # run it once to make the folder
RUN makemkvcon -r info dev:/dev/null  # run it again to download the sdf
# makemkv should download updated sdfs as needed, but we do it once here to minimize the number of times this is done

WORKDIR /djmkv
RUN apt-get install -y linux-headers-generic python3-poetry
COPY src README.md poetry.lock pyproject.toml ./
RUN poetry config virtualenvs.create false && poetry install --no-interaction --only main
ENV PYTHONUNBUFFERED=1
ENTRYPOINT ["python3", "-m", "djmkv.ripper"]
