%define name python27-appsync
%define pythonname appsync
%define version 0.1
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
Requires: nginx memcached gunicorn python27 python27-setuptools python27-webob python27-paste python27-pastedeploy python27-sqlalchemy python27-mako python27-simplejson python27-pastescript python27-mako python27-markusafe python27-chameleon python27-jinja2 python27-pyramid python27-pyramid_jinja python27-pyramid_debugtoolbar python27-repoze.lru python27-translationstring python27-wsgi_intercept python27-zope.component python27-zope.deprecation python27-zope.event python27-zope.interface

Url: https://github.com/mozilla/appsync

%description
App Sync Server.


%prep
%setup -n %{pythonname}-%{version} -n %{pythonname}-%{version}

%build
python2.7 setup.py build

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
python2.7 setup.py install --single-version-externally-managed --root=$RPM_BUILD_ROOT --record=INSTALLED_FILES

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
