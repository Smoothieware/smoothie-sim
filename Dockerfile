# smoothie-sim container image: the toolchain the simulator needs plus the smoothie-sim command.
#   docker run --rm -v "$PWD:/work" ghcr.io/smoothieware/smoothie-sim build
#   docker run --rm -v "$PWD:/work" ghcr.io/smoothieware/smoothie-sim check
FROM ubuntu:24.04
LABEL org.opencontainers.image.source="https://github.com/Smoothieware/smoothie-sim" \
      org.opencontainers.image.description="Run the real Smoothieware firmware core on a PC and check it" \
      org.opencontainers.image.licenses="GPL-2.0-or-later"
RUN apt-get update \
 && apt-get install -y --no-install-recommends g++ make python3 git ca-certificates binutils-arm-none-eabi \
 && rm -rf /var/lib/apt/lists/* \
 && git config --system --add safe.directory '*'
COPY . /src
RUN /src/packaging/stage.sh / /usr && rm -rf /src
# Cache of the cloned Smoothieware tree; mount a volume here to keep it between runs.
RUN mkdir -m 1777 /cache /work
ENV SMOOTHIE_SIM_CACHE=/cache
WORKDIR /work
ENTRYPOINT ["smoothie-sim"]
CMD ["help"]
