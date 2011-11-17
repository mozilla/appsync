import os
import logging

from pyramid.config import Configurator
from mozsvc.config import Config
from mozsvc.util import resolve_name

from appsync.resources import Root


logger = logging.getLogger('appsync')


def main(global_config, **settings):
    config_file = global_config['__file__']
    config_file = os.path.abspath(
                    os.path.normpath(
                    os.path.expandvars(
                        os.path.expanduser(
                        config_file))))

    settings['config'] = config_ = Config(config_file)
    conf_dir, _ = os.path.split(config_file)

    mock_browserid = bool(os.path.expandvars(global_config.get('test', '')))

    config = Configurator(root_factory=Root, settings=settings,
                          autocommit=mock_browserid)

    # adds cornice
    config.include("cornice")

    # adds Mozilla default views
    config.include("mozsvc")

    # local views
    config.scan("appsync.views")

    if mock_browserid:
        # test views
        config.scan("appsync.tests.views")
        config.registry['mock_browserid'] = True

    # initialize the storage backend
    backend = config_.get('storage', 'backend')
    klass = resolve_name(backend)
    config.registry['storage'] = klass(**dict(config_.items('storage')))

    return config.make_wsgi_app()
