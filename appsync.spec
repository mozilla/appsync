%define pyver 26
%define name python%{pyver}-appsync
%define pythonname appsync
%define version 0.7
%define release 1

Summary: App Sync Server.
Name: %{name}
Version: %{version}
Release: %{release}
Source0: %{pythonname}-%{version}.tar.gz
License: MPL
Group: Development/Libraries
BuildRoot: %{_tmppath}/%{pythonname}-%{version}-%{release}-buildroot
Prefix: %{_prefix}
BuildArch: noarch
Vendor: Tarek Ziade <tarek@mozilla.com>
Requires: nginx memcached gunicorn python%{pyver} python%{pyver}-setuptools python%{pyver}-webob python%{pyver}-paste python%{pyver}-pastedeploy python%{pyver}-sqlalchemy python%{pyver}-mako python%{pyver}-simplejson python%{pyver}-pastescript python%{pyver}-mako python%{pyver}-markupsafe python%{pyver}-chameleon python%{pyver}-jinja2 python%{pyver}-pyramid python%{pyver}-pyramid_jinja2 python%{pyver}-pyramid_debugtoolbar python%{pyver}-repoze.lru python%{pyver}-translationstring python%{pyver}-wsgi_intercept python%{pyver}-zope.component python%{pyver}-zope.deprecation python%{pyver}-zope.event python%{pyver}-zope.interface python%{pyver}-venusian python%{pyver}-webtest python%{pyver}-unittest2 python%{pyver}-docutils python%{pyver}-coverage python%{pyver}-pygments python%{pyver}-ordereddict m2crypto


Url: https://github.com/mozilla/appsync

%description
App Sync Server.


%prep
%setup -n %{pythonname}-%{version} -n %{pythonname}-%{version}

%build
python%{pyver} setup.py build

%install

# the config files for Sync apps
mkdir -p %{buildroot}%{_sysconfdir}/appsync
install -m 0644 etc/appsync-prod.ini %{buildroot}%{_sysconfdir}/appsync/appsync-prod.ini

# nginx config
mkdir -p %{buildroot}%{_sysconfdir}/nginx
mkdir -p %{buildroot}%{_sysconfdir}/nginx/conf.d
install -m 0644 etc/appsync.nginx.conf %{buildroot}%{_sysconfdir}/nginx/conf.d/appsync.conf

# logging
mkdir -p %{buildroot}%{_localstatedir}/log
touch %{buildroot}%{_localstatedir}/log/appsync.log

# the app
python%{pyver} setup.py install --single-version-externally-managed --root=$RPM_BUILD_ROOT --record=INSTALLED_FILES

%clean
rm -rf $RPM_BUILD_ROOT

%post
touch %{_localstatedir}/log/appsync.log
chown nginx:nginx %{_localstatedir}/log/appsync.log
chmod 640 %{_localstatedir}/log/appsync.log

%files -f INSTALLED_FILES

%attr(640, nginx, nginx) %ghost %{_localstatedir}/log/appsync.log

%dir %{_sysconfdir}/appsync/

%config(noreplace) %{_sysconfdir}/appsync/*
%config(noreplace) %{_sysconfdir}/nginx/conf.d/appsync.conf

%defattr(-,root,root)
