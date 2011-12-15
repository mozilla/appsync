import logging
import os
import traceback
from ConfigParser import NoSectionError

from webob.dec import wsgify
from webob.exc import HTTPUnauthorized, HTTPServiceUnavailable

from pyramid.settings import asbool

from mozsvc.config import get_configurator
from mozsvc.plugin import load_and_register

from appsync.storage import StorageAuthError, ConnectionError, ServerError


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

    # initializes the cache tool
    try:
        load_and_register("cache", config)
    except NoSectionError:
        pass


class CatchAuthError(object):
    def __init__(self, app, retry_after='120'):
        self.app = app
        if isinstance(retry_after, int):
            retry_after = str(retry_after)
        self.retry_after = retry_after

    @wsgify
    def __call__(self, request):
        try:
            return request.get_response(self.app)
        except (HTTPUnauthorized, StorageAuthError), e:
            logger.debug(traceback.format_exc())
            return HTTPUnauthorized(str(e))
        except (ConnectionError, ServerError, HTTPServiceUnavailable), e:
            logger.error(traceback.format_exc())
            return HTTPServiceUnavailable(str(e),
                                          retry_after=self.retry_after)
        finally:
            if hasattr(request, 'cache'):
                request.cache.cleanup()


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
    retry_after = config.settings('global.retry_after', '120')
    errapp = CatchAuthError(app, retry_after=retry_after)
    errapp.registry = app.registry
    return errapp
