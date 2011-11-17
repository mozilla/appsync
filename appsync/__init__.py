import logging

from pyramid.settings import asbool

from mozsvc.config import get_configurator
from mozsvc.plugin import load_and_register


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


def main(global_config, **settings):
    config = get_configurator(global_config, **settings)

    # Use autocommit if we're in testing mode.
    mock_browserid = asbool(global_config.get('test'))
    if mock_browserid:
        config.autocommit = True

    # Get all the default config for appsync.
    config.include(includeme)

    # Add testing views if we're in testing mode.
    if mock_browserid:
        config.scan("appsync.tests.views")

    return config.make_wsgi_app()
