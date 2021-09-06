# -*- coding: utf-8 -*-
from setuptools import setup

packages = \
['apiens',
 'apiens.di',
 'apiens.testing',
 'apiens.tools',
 'apiens.tools.fastapi',
 'apiens.tools.fastapi.class_based_view',
 'apiens.util',
 'apiens.via',
 'apiens.via.fastapi',
 'apiens.views',
 'apiens.views.crud',
 'apiens.views.mongoquery_crud']

package_data = \
{'': ['*']}

extras_require = \
{'crud': ['pydantic>=1.6.1,<2.0.0',
          'sqlalchemy>=1.3.19,<2.0.0',
          'mongosql>=2.0.11,<3.0.0',
          'sa2schema>=0.1.3,<0.2.0',
          'blinker>=1.4,<2.0'],
 'fastapi': ['fastapi>=0.61.1,<0.62.0']}

setup_kwargs = {
    'name': 'apiens',
    'version': '1.0.1',
    'description': 'Business-logic layer for your API',
    'long_description': None,
    'author': 'Mark Vartanyan',
    'author_email': 'kolypto@gmail.com',
    'maintainer': None,
    'maintainer_email': None,
    'url': 'https://github.com/kolypto/py-apiens',
    'packages': packages,
    'package_data': package_data,
    'extras_require': extras_require,
    'python_requires': '>=3.8,<4.0',
}


setup(**setup_kwargs)
