#! /usr/bin/python
# -*- coding: UTF-8 -*-
"""
Script to import .bok files
Copyright © 2008-2010, Muayyad Alsadi <alsadi@ojuba.org>

    Released under terms of Waqf Public License.
    This program is free software; you can redistribute it and/or modify
    it under the terms of the latest version Waqf Public License as
    published by Ojuba.org.

    This program is distributed in the hope that it will be useful,
    but WITHOUT ANY WARRANTY; without even the implied warranty of
    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.

    The Latest version of the license can be found on
    "http://waqf.ojuba.org/license"

"""

import sys, os, os.path, glob, shutil, re
import sqlite3
from getopt import getopt, GetoptError

# TODO: take shamela prefix
# import Files/special.mdb Files/main.mdb first
# then take bokids eg. -f /opt/emu/apps/shamela-r1/ 100 15001 ..etc.
# if first arg of ShamelaSqlite is a directory,
# getTables should generate tb:fn
# 

def usage():
    print '''\
Usage: %s [-i] [-m DIR] FILES ...
Where:
\t-i\t\t- in-memory
\t-m DIR\t\t- move successfully imported BOK files into DIR
\t--ft-prefix=FOOTER_PREFIX	default is "(¬"
\t--ft-suffix=FOOTER_SUFFIX	default is ")"
\t--ft-leading=[0|1]	should footnote be match at line start only, default is 0
\t--ft-sp=[0|1|2]	no, single or many whitespaces, default is 0 
\t--bft-prefix=FOOTER_PREFIX	footnote anchor in body prefix, default is "(¬"
\t--bft-suffix=FOOTER_SUFFIX	footnote anchor in body suffix, default is ")"
\t--bft-sp=[0|1|2]	no, single or many whitespaces, default is 0 

the generated files will be moved into db in thawab prefix (usually ~/.thawab/db/)
''' % os.path.basename(sys.argv[0])

try:
  opts, args = getopt(sys.argv[1:], "im:", ["help", 'ft-prefix=', 'ft-suffix=', 'bft-prefix=', 'bft-suffix=', 'ft-leading=', 'ft-sp=', 'bft-sp='])
except GetoptError, err:
  print str(err) # will print something like "option -a not recognized"
  usage()
  sys.exit(1)

if not args:
  print "please provide at least one .bok files"
  usage()
  sys.exit(1)

opts=dict(opts)

def progress(msg, p, *a, **kw): print " ** [%g%% completed] %s" % (p,msg)

from Thawab.core import ThawabMan
from Thawab.shamelaUtils import ShamelaSqlite,shamelaImport
th=ThawabMan()
thprefix=th.prefixes[0]

if not opts.has_key('-i'): db_fn=os.path.expanduser('~/bok2sql.db')
else: db_fn=None

#    ¬ U+00AC NOT SIGN
ft_prefix=opts.get('--ft-prefix','(¬').decode('utf-8'); ft_prefix_len=len(ft_prefix)
ft_suffix=opts.get('--ft-suffix',')').decode('utf-8'); ft_suffix_len=len(ft_suffix)
ft_sp=[u'', ur'\s?' , ur'\s*'][int(opts.get('--ft-sp','0'))]
ft_at_line_start=int(opts.get('--ft-leading','0'))
footnote_re=(ft_at_line_start and u'^\s*' or u'') + re.escape(ft_prefix)+ft_sp+ur'(\d+)'+ft_sp+re.escape(ft_suffix)

bft_prefix=opts.get('--bft-prefix','(¬').decode('utf-8');
bft_suffix=opts.get('--bft-suffix',')').decode('utf-8');
bft_sp=[u'', ur'\s?' , ur'\s*'][int(opts.get('--bft-sp','0'))]
body_footnote_re=re.escape(bft_prefix)+bft_sp+ur'(\d+)'+bft_sp+re.escape(bft_suffix)



for fn in args:
  if db_fn:
    if os.path.exists(db_fn): os.unlink(db_fn)
    cn=sqlite3.connect(db_fn, isolation_level=None)
  else: cn=None
  sh=ShamelaSqlite(fn, cn, 0 , 0, progress)
  sh.toSqlite()
  for bkid in sh.getBookIds():
    ki=th.mktemp()
    c=ki.seek(-1,-1)
    
    m=shamelaImport(c, sh, bkid, footnote_re, body_footnote_re, ft_prefix_len, ft_suffix_len)
    c.flush()
    print "moving %s to %s" % (ki.uri, os.path.join(thprefix,'db', m['kitab']+u"-"+m['version']+u".ki"))
    shutil.move(ki.uri, os.path.join(thprefix,'db', m['kitab']+u"-"+m['version']+u".ki"))
  if opts.has_key('-m'):
    dd=opts['-m']
    if not os.path.isdir(dd):
      try: os.makedirs(dd)
      except OSError: pass
    if os.path.isdir(dd):
      dst=os.path.join(dd,os.path.basename(fn))
      print "moving %s to %s" % (fn,dst)
      shutil.move(fn, dst)
    else: print "could not move .bok files, target directory does not exists"

