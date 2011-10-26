import os

from pyramid.config import Configurator
from mozsvc.config import Config

from appsync.resources import Root

# XXX user resolve_name from mozsvc
from appsync.util import json_renderer, resolve_name


def main(global_config, **settings):
    config_file = global_config['__file__']
    config_file = os.path.abspath(
                    os.path.normpath(
                    os.path.expandvars(
                        os.path.expanduser(
                        config_file))))

    settings['config'] = config_ = Config(config_file)
    conf_dir, _ = os.path.split(config_file)

    config = Configurator(root_factory=Root, settings=settings)

    # custom renderer
    config.add_renderer('simplejson', json_renderer)

    # adds cornice
    config.include("cornice")

    # adds Mozilla default views
    config.include("mozsvc")

    # local views
    config.scan("appsync.views")

    # initialize the storage
    backend = config_.get('storage', 'backend')
    klass = resolve_name(backend)
    config.registry['storage'] = klass(**dict(config_.items('storage')))

    return config.make_wsgi_app()
