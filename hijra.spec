Name: hijra
Summary: Hijri Islamic Calendar utils in python
URL: http://hijra.ojuba.org
Version: 0.1.10
Release: 1%{?dist}
Source0: %{name}-%{version}.tar.bz2
License: Waqf
Group: System Environment/Base
BuildRoot: %{_tmppath}/%{name}-%{version}-%{release}-root-%(%{__id_u} -n)
BuildRequires: gettext
BuildRequires: python, python-setuptools

%{!?python_sitelib: %define python_sitelib %(%{__python} -c "from distutils.sysconfig import get_python_lib; print get_python_lib(1)")}

%description
This is Hijra package from hijra.ojuba.org
It provides Hijri/Islamic Calendar routines and utils in python

%package python
Group: System Environment/Base
Summary: Hijri Islamic Calendar converting functions for python
BuildArch: noarch
Requires: python, setuptool
%description python
This is Hijra package from hijra.ojuba.org

Hijri Islamic Calendar converting functions,
an enhanced algorithm designed by Muayyad Saleh Alsadi<alsadi@gmail.com>
it can be used to implement apps, gdesklets or karamba ..etc

This algorithm is based on integer operations
which that there is no round errors (given accurate coefficients)
the accuracy of this algorithm is based on 3 constants (p,q and a)
where p/q is the full months percentage [ gcd(p,q) must be 1 ]
currently it's set to 191/360 which mean that there is 191 months
having 30 days in a span of 360 years, other months are 29 days.
and a is just a shift.

%package applet
Summary: Hijri Tray Applet for GNOME (also works with KDE)
Group: System Environment/Base
BuildArch: noarch
# TODO: is it better to say gnome-python2-extras ?
Requires: python, setuptool, pygtk2, gnome-python2-libegg, notify-python
Requires: hijra-python
Requires(post): desktop-file-utils
%description applet
Hijri Tray Applet for GNOME (also works with KDE)
That uses Hijra Algorithm by Muayyad Saleh Alsadi<alsadi@gmail.com>
provided by python-hijra package

%prep
%setup -q
%build

%install
rm -rf $RPM_BUILD_ROOT

mv HijriApplet.py HijriApplet
chmod +x HijriApplet
%{__python} setup.py install \
        --root=$RPM_BUILD_ROOT \
        --optimize=2
%post applet

%clean
rm -rf $RPM_BUILD_ROOT

%files python
/usr/share/doc/hijra-python/*
%{python_sitelib}/*
%files applet
/usr/bin/*
/etc/xdg/autostart/*
%changelog

* Sun Aug 03 2008  Muayyad Saleh AlSadi <alsadi@ojuba.org> - 0.1.10-1
- Auto update date
- Fix consistency bug

* Tue Jul 22 2008  Muayyad Saleh AlSadi <alsadi@ojuba.org> - 0.1.9-1
- Auto update date

* Sat Jun 28 2008  Muayyad Saleh AlSadi <alsadi@ojuba.org> - 0.1.8-1
- Initial packing

