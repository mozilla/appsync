"""This is a setup for serving up the Open Web Apps static files

This is intended for testing, when you want to setup a site that
encompasses the entirety of what https://myapps.mozillalabs.com will
serve up
"""

import os
from paste.urlparser import StaticURLParser
from webob.dec import wsgify
from appsync.getmanifest import GetManifest


class MyAppsTest(object):
    def __init__(self, app, openwebapps, apps):
        self.app = app
        self.openwebapps = openwebapps
        self.apps = apps

    @wsgify
    def __call__(self, req):
        orig_req = req.copy()
        base = req.application_url
        if req.path_info.startswith('/getmanifest'):
            return GetManifest()
        if req.path_info.startswith('/sync'):
            path = os.path.join(self.openwebapps)
        elif req.path_info.startswith('/apps') and self.apps:
            path = self.apps
            req.path_info_pop()
        else:
            path = os.path.join(self.openwebapps, 'site')
        static_app = StaticURLParser(path)
        resp = req.get_response(static_app)
        if resp.status_int == 200:
            ct = resp.content_type.lower().split(';')[0].strip()
            if ct in ('text/html', 'application/javascript',
                      'text/javascript'):
                resp.body = \
                    resp.body.replace('https://myapps.mozillalabs.com', base)
            resp.cache_expires()
        if resp.status_int == 404:
            resp = orig_req.get_response(self.app)
        return resp


def main(app, global_conf, **settings):
    if not settings.get('openwebapps'):
        raise ValueError('You must give the openwebapps configuration value')
    orig = openwebapps = settings['openwebapps']
    openwebapps = os.path.expandvars(openwebapps)
    openwebapps = os.path.expanduser(openwebapps)
    if (not os.path.exists(openwebapps)
        or not os.path.exists(os.path.join(openwebapps,
            'site/jsapi/include.js'))):
        raise ValueError("The openwebapps value (%s / %s) "
                         "doesn't seem to be a valid checkout"
                         % (orig, openwebapps))
    apps = os.path.expandvars(os.path.expanduser(settings.get('apps', '')))
    return MyAppsTest(app, openwebapps, apps)
