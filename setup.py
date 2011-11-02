import os

from setuptools import setup, find_packages

here = os.path.abspath(os.path.dirname(__file__))

with open(os.path.join(here, 'README.txt')) as f:
    README = f.read()

with open(os.path.join(here, 'CHANGES.txt')) as f:
    CHANGES = f.read()

requires = ['cornice', 'mozsvc', 'WebTest', 'simplejson', 'SQLAlchemy']


setup(name='appsync',
      version='0.1',
      description='appsync',
      long_description=README + '\n\n' +  CHANGES,
      classifiers=[
        "Programming Language :: Python",
        "Framework :: Pylons",
        "Topic :: Internet :: WWW/HTTP",
        "Topic :: Internet :: WWW/HTTP :: WSGI :: Application",
        ],
      author='',
      author_email='',
      url='',
      keywords='web pyramid pylons',
      packages=find_packages(),
      include_package_data=True,
      zip_safe=False,
      install_requires=requires,
      tests_require=requires,
      test_suite="appsync",
      entry_points = """\
      [paste.app_factory]
      main = appsync:main
      getmanifest = appsync.getmanifest:main
      """,
      paster_plugins=['pyramid'],
      )
