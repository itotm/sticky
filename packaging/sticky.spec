Name:           sticky
Version:        1.33
Release:        4%{?dist}
Summary:        Sticky notes app with a KDE-style look

License:        GPL-2.0-only
URL:            https://github.com/itotm/sticky
Source0:        %{name}-%{version}.tar.gz

BuildArch:      noarch

BuildRequires:  meson
BuildRequires:  gettext
BuildRequires:  desktop-file-utils
BuildRequires:  python3-devel

Requires:       python3
Requires:       python3-gobject
Requires:       gobject-introspection
Requires:       gtk3
Requires:       gspell
Requires:       xapps
Requires:       python3-xapps-overrides
Requires:       python3-xapp

%description
Sticky notes on the desktop, with groups, a manager window, formatting,
checklists, backups and a tray icon. Linux Mint's Sticky, changed to fit a
KDE Plasma desktop: notes with rounded corners like Breeze windows, a manager
with the KWin title bar, a toolbar like the KDE applications, softer note
colors and freedesktop icon names.

%prep
%autosetup
sed -i 's/__DEB_VERSION__/%{version}-%{release}/' usr/lib/sticky/sticky.py

%build
%meson
%meson_build

%install
%meson_install
%py_byte_compile %{python3} %{buildroot}%{_prefix}/lib/sticky
%find_lang %{name}

%check
desktop-file-validate %{buildroot}%{_datadir}/applications/sticky.desktop
desktop-file-validate %{buildroot}%{_sysconfdir}/xdg/autostart/sticky.desktop

%files -f %{name}.lang
%license COPYING
%doc README.md
%{_bindir}/sticky
%{_prefix}/lib/sticky/
%{_datadir}/sticky/
%{_datadir}/applications/sticky.desktop
%{_datadir}/dbus-1/services/org.x.sticky.service
%{_datadir}/glib-2.0/schemas/org.x.sticky.gschema.xml
%{_datadir}/icons/hicolor/scalable/apps/sticky.svg
%{_datadir}/icons/hicolor/scalable/apps/sticky-symbolic.svg
%{_datadir}/icons/hicolor/scalable/status/sticky-*.svg
%config(noreplace) %{_sysconfdir}/xdg/autostart/sticky.desktop

%changelog
* Fri Oct 16 2026 itotm <1804363+itotm@users.noreply.github.com> - 1.33-4
- Find the data files from the install prefix, for the new Flatpak build
- Native file dialogs for import and export

* Fri Oct 16 2026 itotm <1804363+itotm@users.noreply.github.com> - 1.33-3
- Notes reopen where they were moved instead of at their old position
- Notes no longer grow by the shadow size each time they are hidden and shown

* Fri Oct 16 2026 itotm <1804363+itotm@users.noreply.github.com> - 1.33-2
- Tray icon as a StatusNotifierItem with a native Plasma menu; clicks on the
  XEmbed icon got lost under Wayland
- Call the app Sticky in every language

* Thu Oct 15 2026 itotm <1804363+itotm@users.noreply.github.com> - 1.33-1
- First build for Fedora, based on Linux Mint's Sticky 1.33
- Notes with rounded corners and a softer shadow, like Breeze windows
- Softer, pastel note colors and highlight
- Manager with the KWin title bar and a KDE-style toolbar instead of the GTK header bar
- Freedesktop icon names instead of the xsi icons, which Fedora does not ship
