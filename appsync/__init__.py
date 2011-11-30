import logging
import os

from webob.dec import wsgify
from webob.exc import HTTPUnauthorized

from pyramid.settings import asbool

from mozsvc.config import get_configurator
from mozsvc.plugin import load_and_register
from mozsvc.middlewares import CatchErrorMiddleware

from appsync.storage import StorageAuthError


logger = logging.getLogger('appsync')


def includeme(config):
    # adds cornice
    config.include("cornice")

    # adds Mozilla default views
    config.include("mozsvc")

    # adds local views
    config.scan("appsync.views")

    # initializes the storage backend
    load_and_register("storage", config)


# XXX this should be backported to mozsvc
class CatchErrorMiddleware2(CatchErrorMiddleware):
    def __init__(self, app, config):
        import logging
        from mozsvc.middlewares import _resolve_name
        self.app = app
        logger_name = config.get('global.logger_name', 'root')
        self.logger = logging.getLogger(logger_name)
        hook = config.get('global.logger_hook')
        if hook is not None:
            self.hook = _resolve_name(hook)
        else:
            self.hook = None
        self.ctype = config.get('global.logger_type', 'application/json')


class CatchAuthError(object):
    def __init__(self, app):
        self.app = app

    @wsgify
    def __call__(self, request):
        try:
            return request.get_response(self.app)
        except StorageAuthError:
            return HTTPUnauthorized()


def main(global_config, **settings):
    config = get_configurator(global_config, **settings)

    # Use autocommit if we're in testing mode.
    mock_browserid = asbool(os.path.expandvars(global_config.get('test', '')))
    if mock_browserid:
        config.autocommit = True

    # Get all the default config for appsync.
    config.include(includeme)

    # Add testing views if we're in testing mode.
    if mock_browserid:
        config.scan("appsync.tests.views")
        config.registry['mock_browserid'] = True

    app = config.make_wsgi_app()
    errapp = CatchAuthError(app)
    errapp = CatchErrorMiddleware2(errapp, config.registry.settings)
    errapp.registry = app.registry
    return errapp
