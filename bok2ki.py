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

import sys, os, os.path, glob, shutil
import sqlite3
from getopt import getopt, GetoptError

thprefix=os.path.expanduser('~/.thawab')
def usage():
    print '''\
Usage: %s [-i] [-m DIR] FILES ...
Where:
\t-i\t\t- in-memory
\t-m DIR\t\t- move successfully imported files into DIR

the generated files will be moved into ~/.thawab/db/
''' % os.path.basename(sys.argv[0])

try:
  opts, args = getopt(sys.argv[1:], "im:", ["help"])
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

if not opts.has_key('-i'): db_fn=os.path.expanduser('~/bok2sql.db')
else: db_fn=None

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
    m=shamelaImport(c, sh, bkid)
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

