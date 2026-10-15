#!/bin/sh
# Build the RPM in a clean Fedora container.
#   ./packaging/build-rpm.sh [fedora release]   (default: 44)
set -eu

release=${1:-44}
root=$(cd "$(dirname "$0")/.." && pwd)
spec="$root/packaging/sticky.spec"

version=$(sed -n "s/^project('sticky', version : '\([^']*\)'.*/\1/p" "$root/meson.build")
spec_version=$(sed -n 's/^Version: *//p' "$spec")
if [ "$version" != "$spec_version" ]; then
    echo "Version mismatch: meson.build has $version, the spec has $spec_version" >&2
    exit 1
fi

out="$root/dist"
work=$(mktemp -d)
trap 'rm -rf "$work"' EXIT
mkdir -p "$out" "$work/sources"

name="sticky-$version"
cd "$root"
git ls-files -co --exclude-standard | grep -v '^dist/' |
    tar -T - --transform "s,^,$name/," -czf "$work/sources/$name.tar.gz"
cp "$spec" "$work/sources/"

podman run --rm --security-opt label=disable \
    -v "$work/sources":/sources:ro -v "$out":/out \
    "registry.fedoraproject.org/fedora:$release" sh -euc '
        dnf -y -q install rpm-build "dnf-command(builddep)"
        dnf -y -q builddep /sources/sticky.spec
        rpmbuild -bb /sources/sticky.spec \
            --define "_sourcedir /sources" --define "_rpmdir /out" --define "_build_name_fmt %%{NAME}-%%{VERSION}-%%{RELEASE}.%%{ARCH}.rpm"'

ls -1 "$out"/*.rpm
