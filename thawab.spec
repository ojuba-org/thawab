Name: thawab
Summary: Thawab Arabic/Islamic encyclopedia system
URL: http://thawab.ojuba.org/
Version: 3.0.2
Release: 1%{?dist}
Source0: http://git.ojuba.org/cgit/%{name}/snapshot/%{name}-%{version}.tar.bz2
License: Waqf
Group: System Environment/Base
BuildArch: noarch
BuildRoot: %{_tmppath}/%{name}-%{version}-%{release}-root-%(%{__id_u} -n)
Requires: python, python-whoosh, python-okasha, islamic-menus, python-othman, pygtk2, pywebkitgtk, pyparsing
BuildRequires: gettext
BuildRequires: python

%{!?python_sitelib: %global python_sitelib %(%{__python} -c "from distutils.sysconfig import get_python_lib; print get_python_lib(1)")}

%description
Thawab Arabic/Islamic encyclopedia system

%package -n thawab-gtk
Group:   User Interface/Desktops
Summary: WebkitGtk interface for Thawab the Arabic/Islamic encyclopedia system 
Requires: %{name}, 
%description -n thawab-gtk
GUI interface based WebkitGtk for Thawab the Arabic/Islamic encyclopedia system 

%prep
%setup -q
%build
make %{?_smp_mflags}

%install
rm -rf $RPM_BUILD_ROOT
%makeinstall DESTDIR=$RPM_BUILD_ROOT

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

%clean
rm -rf $RPM_BUILD_ROOT

%files
%defattr(-,root,root,-)
%doc LICENSE-ar.txt LICENSE-en readme
%{_bindir}/thawab-gtk
%{python_sitelib}/Thawab/*
%{python_sitelib}/*.egg-info
%{_datadir}/thawab/
%{_datadir}/icons/hicolor/*/apps/*.png
%{_datadir}/icons/hicolor/*/apps/*.svg
%{_datadir}/applications/*.desktop
%{_datadir}/locale/*/*/*.mo

%changelog
* Sat Jun 12 2010  Muayyad Saleh AlSadi <alsadi@ojuba.org> - 3.0.2-1
- initial packing

