import os

from pyramid.config import Configurator
from mozsvc.config import Config

from appsync.resources import Root
from appsync.util import json_renderer
from appsync.storage import MemDatabase


def main(global_config, **settings):
    config_file = global_config['__file__']
    config_file = os.path.abspath(
                    os.path.normpath(
                    os.path.expandvars(
                        os.path.expanduser(
                        config_file))))

    settings['config'] = config = Config(config_file)
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
    config.registry['storage'] = MemDatabase()

    return config.make_wsgi_app()
