#! /usr/bin/python3
import sys, os, os.path
from distutils.core import setup
from glob import glob

# to install type: 
# python setup.py install --root=/

def no_empty(l):
  return [i_j for i_j in l if i_j[1]]

def recusive_data_dir(to, src, l=None):
  D=glob(os.path.join(src,'*'))
  files=[i for i in D if os.path.isfile(i)]
  dirs=[i for i in D if os.path.isdir(i)]
  if l==None: l=[]
  l.append( (to , files ) )
  for d in dirs: recusive_data_dir( os.path.join(to,os.path.basename(d)), d , l)
  return l

locales=[('share/'+i,[''+i+'/thawab.mo',]) for i in glob('locale/*/LC_MESSAGES')]
data_files=no_empty(recusive_data_dir('share/thawab/', 'thawab-data'))
data_files.extend(locales)
setup (name='thawab', version='3.0.10',
      description='Thawab Arabic/Islamic encyclopedia system',
      author='Muayyad Saleh Alsadi',
      author_email='alsadi@ojuba.org',
      url='http://thawab.ojuba.org/',
      license='Waqf',
      packages=['Thawab'],
      scripts=['thawab-gtk','thawab-server'],
      classifiers=[
          'Development Status :: 4 - Beta',
          'Intended Audience :: End Users/Desktop',
          'Operating System :: POSIX',
          'Programming Language :: Python',
          ],
      data_files=data_files
)


