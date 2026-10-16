#!/bin/sh
# Build the Flatpak bundle with flatpak-builder, or with org.flatpak.Builder
# from Flathub when it isn't installed. Needs org.gnome.Sdk//51.
#   ./packaging/build-flatpak.sh
set -eu

root=$(cd "$(dirname "$0")/.." && pwd)
spec="$root/packaging/sticky.spec"
app_id=io.github.itotm.Sticky

version=$(sed -n "s/^project('sticky', version : '\([^']*\)'.*/\1/p" "$root/meson.build")
spec_version=$(sed -n 's/^Version: *//p' "$spec")
if [ "$version" != "$spec_version" ]; then
    echo "Version mismatch: meson.build has $version, the spec has $spec_version" >&2
    exit 1
fi
# Same version as the RPM, e.g. 1.33-4
release=$(sed -n 's/^Release: *\([0-9]*\).*/\1/p' "$spec")
full="$version-$release"

builder() {
    if command -v flatpak-builder >/dev/null; then
        flatpak-builder "$@"
    else
        flatpak run org.flatpak.Builder "$@"
    fi
}

# Under the source tree and not in /tmp, which the Flathub builder doesn't share
state="$root/.flatpak-builder"
work="$state/work"
out="$root/dist"
rm -rf "$work"
mkdir -p "$work/sticky" "$out"

cd "$root"
git ls-files -co --exclude-standard | grep -v '^dist/' | tar -T - -cf - | tar -xf - -C "$work/sticky"
sed -i "s/__DEB_VERSION__/$full/" "$work/sticky/usr/lib/sticky/sticky.py"
cp packaging/flatpak/$app_id.yml packaging/flatpak/*.patch "$work/"
sed -e "s/@VERSION@/$full/" -e "s/@DATE@/$(git log -1 --format=%cs)/" \
    packaging/flatpak/$app_id.metainfo.xml > "$work/$app_id.metainfo.xml"

builder --force-clean --default-branch=stable --state-dir="$state" --repo="$work/repo" \
    "$work/build" "$work/$app_id.yml"
flatpak build-bundle --runtime-repo=https://dl.flathub.org/repo/flathub.flatpakrepo \
    "$work/repo" "$out/sticky-$full.x86_64.flatpak" $app_id stable

ls -1 "$out"/*.flatpak
