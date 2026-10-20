# Installation

smoothie-sim supports Linux. Every release ships the same architecture-independent contents in four forms; the simulator itself is compiled on your machine by `smoothie-sim build`, so you need `g++`, `make`, `python3` and `git` (the packages below pull them in). macOS is not supported.

Releases: <https://github.com/Smoothieware/smoothie-sim/releases>. Each one lists `SHA256SUMS`.

| Form | Install |
| --- | --- |
| Install script (any Linux) | `curl -fsSL https://github.com/Smoothieware/smoothie-sim/releases/latest/download/install.sh \| sh` installs under `~/.local` (`PREFIX=/usr/local` to change, `SMOOTHIE_SIM_VERSION=0.1.0` to pin). It checks the tarball against `SHA256SUMS`. |
| Tarball | `smoothie-sim-VERSION.tar.gz`: `bin/smoothie-sim` and `share/smoothie-sim/`. Unpack anywhere and run `bin/smoothie-sim`. |
| Debian, Ubuntu | `sudo apt install ./smoothie-sim_VERSION_all.deb` |
| Fedora, RHEL | `sudo dnf install ./smoothie-sim-VERSION-1.noarch.rpm` |
| Container image | `docker run --rm -v "$PWD:/work" ghcr.io/smoothieware/smoothie-sim check` (amd64 and arm64) |

## Use

```sh
smoothie-sim build        # clones Smoothieware edge into ~/.cache/smoothie-sim/fw, builds ./build/smoothie-sim
smoothie-sim check        # writes ./out/report.html and ./out/summary.md
```

`smoothie-sim build SMOOTHIE_SRC=/path/to/Smoothieware -j8` builds your own tree; `smoothie-sim check build/smoothie-sim /path/to/Smoothieware - out` checks it. Both accept everything the `Makefile` and `run_checks.sh` document in [Getting started](getting-started.md). `SMOOTHIE_SIM_CACHE` moves the cache of the cloned firmware.

In the container, add `-u "$(id -u):$(id -g)"` to get files you own, and `-v smoothie-sim-cache:/cache` to keep the firmware clone between runs. The image also has `binutils-arm-none-eabi` for the RAM and flash check.

## Releasing (maintainers)

1. Put the changes under `[Unreleased]` in `CHANGELOG.md`, rename that heading to `[X.Y.Z] - date`, add a new empty `[Unreleased]`, and set `VERSION` to `X.Y.Z`.
2. Merge to `main`; the `release` workflow builds and smoke-tests the packages on every push.
3. Tag `vX.Y.Z` on that commit and push the tag. The workflow checks the tag matches `VERSION`, then publishes the container image and creates the GitHub release with the packages, `install.sh` and `SHA256SUMS`; the release notes are the changelog section.
