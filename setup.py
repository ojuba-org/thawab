#! /usr/bin/python
import sys, os
from distutils.core import setup
from glob import glob

# to install type: 
# python setup.py install --root=/

locales=map(lambda i: ('share/'+i,[''+i+'/thawab.mo',]),glob('locale/*/LC_MESSAGES'))
data_files=[
  ('share/thawab/thawab-files/media/',glob('thawab-files/media/*.js')+glob('thawab-files/media/*.css')),
  ('share/thawab/thawab-files/media/img',glob('thawab-files/media/img/*')),
  ('share/thawab/thawab-files/templates/',glob('thawab-files/templates/*.html')),
]
data_files.extend(locales)
setup (name='thawab', version='0.2.2',
      description='Thawab Arabic/Islamic encyclopedia system',
      author='Muayyad Saleh Alsadi',
      author_email='alsadi@ojuba.org',
      url='http://tawab.ojuba.org/',
      license='Waqf',
      packages=['Thawab'],
      scripts=['thawab-gtk'],
      classifiers=[
          'Development Status :: 4 - Beta',
          'Intended Audience :: End Users/Desktop',
          'Operating System :: POSIX',
          'Programming Language :: Python',
          ],
      data_files=data_files
)


