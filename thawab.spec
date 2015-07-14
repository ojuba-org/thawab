%global owner ojuba-org
%global commit #Write commit number here

Name: thawab
Summary: Arabic/Islamic encyclopedia system
Summary(ar): نظام موسوعي عربي/إسلامي
URL: http://ojuba.org/
Version: 3.2.0
Release: 3%{?dist}
Source0: https://github.com/%{owner}/%{name}/archive/%{commit}/%{name}-%{commit}.tar.gz
License: WAQFv2
BuildArch: noarch
Requires: python-whoosh >= 1.7.2
Requires: python-okasha >= 0.2.3
Requires: pygobject3 >= 3.0.2
Requires: python
Requires: mdbtools
Requires: python-paste
Requires: islamic-menus
Requires: python-othman
BuildRequires: gettext
BuildRequires: python2-devel
BuildRequires: perl
BuildRequires: ImageMagick
BuildRequires: intltool

%description
Thawab Arabic/Islamic encyclopedia system

%prep
%setup -q -n %{name}-%{commit}

%build
bash update-manual-from-site.sh
make %{?_smp_mflags}

%install
%make_install

%post
touch --no-create %{_datadir}/icons/hicolor || :
if [ -x %{_bindir}/gtk-update-icon-cache ] ; then
%{_bindir}/gtk-update-icon-cache --quiet %{_datadir}/icons/hicolor || :
fi

%postun
touch --no-create %{_datadir}/icons/hicolor || :
if [ -x %{_bindir}/gtk-update-icon-cache ] ; then
%{_bindir}/gtk-update-icon-cache --quiet %{_datadir}/icons/hicolor || :
fi

%files
%license waqf2-ar.pdf
%doc waqf2-ar.pdf readme
%{_bindir}/thawab-gtk
%{_bindir}/thawab-server
%{python2_sitelib}/Thawab/*
%{python2_sitelib}/*.egg-info
%{_datadir}/thawab/
%{_datadir}/icons/hicolor/*/apps/*.png
%{_datadir}/icons/hicolor/*/apps/*.svg
%{_datadir}/applications/*.desktop
%{_datadir}/locale/*/*/*.mo

%changelog
* Tue Jul 14 2015 Mosaab Alzoubi <moceap@hotmail.com> - 3.2.0-3
- Enhance summary
- Remove Group tag
- Add Arabic summary and description
- Improve %%install section
- Remove %%clean section
- Remove old attr way
- Use %%license

* Tue Jul 14 2015 Mosaab Alzoubi <moceap@hotmail.com> - 3.2.0-2
- Add some BRs

* Sat Feb 14 2015  Mosaab Alzoubi <moceap@hotmail.com> - 3.2.0-1
- Add Thawab Server.

* Sat Feb 15 2014  Mosaab Alzoubi <moceap@hotmail.com> - 3.1.1-2
- Genera Revision.

* Mon Jun 1 2012  Muayyad Saleh AlSadi <alsadi@ojuba.org> - 3.1.1-1
- port to gtk 3

* Mon Nov 1 2010  Muayyad Saleh AlSadi <alsadi@ojuba.org> - 3.0.10-1
- update to whoosh 1.x.y

* Mon Jul 26 2010  Muayyad Saleh AlSadi <alsadi@ojuba.org> - 3.0.8-1
- activate cancel button in import window
- only reload index after new import
- css: hide overflow in minisearch

* Sun Jul 4 2010  Muayyad Saleh AlSadi <alsadi@ojuba.org> - 3.0.7-1
- update to latest stable release
- activate footnotes links
- opens external links with default browser
- print button
- add zoom buttons
- auto reload after import
- change search query syntax
- add manual
- add filter to book listing

* Sun Jul 4 2010  Muayyad Saleh AlSadi <alsadi@ojuba.org> - 3.0.5-1
- highlight minisearch text
- reload meta after import
- fix some importing bugs
- use connection-per-thread in core.py
- static-like pages

* Fri Jun 18 2010  Muayyad Saleh AlSadi <alsadi@ojuba.org> - 3.0.4-1
- load books from /usr/share/thawab/db/
- limit search results to 500
- notfy user for non-indexed books

* Thu Jun 17 2010  Muayyad Saleh AlSadi <alsadi@ojuba.org> - 3.0.3-1
- add missing Requires
- hide mini search if not indexed

* Sat Jun 12 2010  Muayyad Saleh AlSadi <alsadi@ojuba.org> - 3.0.2-1
- initial packing

