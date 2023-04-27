#! /usr/bin/python3
# -*- coding: UTF-8 -*-
"""
Setting meta data for thawab files
Copyright © 2010, Muayyad Alsadi <alsadi@ojuba.org>

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
import sys, os, os.path
import Thawab.core

from getopt import getopt, GetoptError

def usage():
  print('''\
Usage: %s [plbvRrtayAYBVck] VALUE ... FILES ...
Where:
\t-p VALUE\t set repo name to VALUE
\t-l VALUE\t set language name to VALUE
\t-b VALUE\t set kitab name to VALUE
\t-v VALUE\t set version name to VALUE
\t-R VALUE\t set release major name to VALUE
\t-r VALUE\t set release minor name to VALUE
\t-t VALUE\t set kitab type to VALUE
\t-a VALUE\t set author name to VALUE
\t-y VALUE\t set author death year to VALUE
\t-A VALUE\t set original kitab author name to VALUE
\t-Y VALUE\t set original kitab author death year to VALUE
\t-B VALUE\t set original kitab name to VALUE
\t-V VALUE\t set original kitab version to VALUE
\t-c VALUE\t set classification to VALUE
\t-k VALUE\t set keywords to VALUE
''' % os.path.basename(sys.argv[0]))

meta_keys={
  '-p':'repo', '-l':'lang', '-b':'kitab',
  '-v':'version', '-R':'releaseMajor', '-r':'releaseMinor',
  '-t':'type', '-a':'author', '-y':'year',
  '-A':'originalAuthor', '-Y':'originalYear', '-B':'originalKitab', '-V':'originalVersion',
  '-c':'classification', '-k':'keywords'
}
metas=set(meta_keys.values())
try:
  opts, args = getopt(sys.argv[1:], "hp:l:b:v:r:R:t:a:y:A:Y:B:V:c:k:", ["help"])
except GetoptError as err:
  print(str(err)) # will print something like "option -a not recognized"
  usage()
  sys.exit(1)
opts=dict([(meta_keys.get(i,i),j) for i,j in opts])
if "-h" in opts or "--help" in opts or len(opts)==0 or not args:
  usage()
  sys.exit(1)

th=Thawab.core.ThawabMan()
for uri in args:
  ki=th.getKitabByUri(uri)
  #print ki.meta
  for i in opts:
    ki.meta[i]=opts[i]
  #print ki.meta
  ki.setMCache(ki.meta)

