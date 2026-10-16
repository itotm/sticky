#!/bin/sh
# Build the .deb in a clean Debian container.
#   ./packaging/build-deb.sh [debian release]   (default: 13)
set -eu

release=${1:-13}
root=$(cd "$(dirname "$0")/.." && pwd)

version=$(sed -n "s/^project('sticky', version : '\([^']*\)'.*/\1/p" "$root/meson.build")
deb_version=$(sed -n '1s/^sticky (\([^)]*\)).*/\1/p' "$root/debian/changelog")
case "$deb_version" in
    "$version"|"$version"+*) ;;
    *)
        echo "Version mismatch: meson.build has $version, debian/changelog has $deb_version" >&2
        exit 1
        ;;
esac

out="$root/dist"
work=$(mktemp -d)
trap 'rm -rf "$work"' EXIT
mkdir -p "$out" "$work/sources"

name="sticky-$deb_version"
cd "$root"
git ls-files -co --exclude-standard | grep -v '^dist/' |
    tar -T - --transform "s,^,$name/," -czf "$work/sources/$name.tar.gz"

podman run --rm --security-opt label=disable \
    -v "$work/sources":/sources:ro -v "$out":/out \
    "docker.io/library/debian:$release" sh -euc '
        export DEBIAN_FRONTEND=noninteractive
        apt-get -qq update
        apt-get -qq -y install --no-install-recommends build-essential devscripts equivs >/dev/null
        mkdir /build && cd /build
        tar -xzf /sources/*.tar.gz
        cd sticky-*
        mk-build-deps -i -r -t "apt-get -qq -y --no-install-recommends" debian/control >/dev/null
        dpkg-buildpackage -b -uc -us
        cp ../*.deb /out/'

ls -1 "$out"/*.deb
