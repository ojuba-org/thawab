# -*- coding: UTF-8 -*-
"""
Copyright © 2008, Muayyad Alsadi <alsadi@ojuba.org>

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
import time, re
####################################
header_re=re.compile(r'^\s*(=+)\s*(.+?)\s*\1\s*$')
def importFromWiki(c, wiki):
  """import a wiki-like into a thawab"""
  ki=c.ki
  txt=""
  parents=[ki.root]
  wikidepths=[0]
  title=None
  wiki_started=0
  meta={'cache_hash': time.time(),'repo': u'_local',
  'lang':None,'kitab':None,'version':u'1', 'releaseMajor':u'0', 'releaseMinor':u'0',
  'author':None, 'year':0, 'originalAuthor':None,'originalYear':0,
  'originalKitab':None, 'originalVersion':None,
  'classification':u'_misc'}
  for l in wiki:
    #l=l.decode('utf-8')
    if wiki_started==0:
      if l.startswith('@'):
        kv=l.split('=',1)
        key=kv[0][1:].strip()
        if len(kv)==2: value=kv[1].strip()
        meta[key]=value
        continue
      else:
        wiki_started=1
    m=header_re.match(l)
    if not m:
      # textbody line: add the line to accumelated textbody variable
      txt+=l
    else:
      # new header:
      # add the accumelated textbody of a previous header (if exists) to the Kitab 
      if txt and title:
        c.appendNode(parents[-1], txt, {'textbody':None})
      # elif txt and not title: pass # it's leading noise, as title can't be empty because of + in the RE
      # reset the accumelated textbody
      txt=""
      # now get the title of matched by RE
      title=m.group(2)
      newwikidepth=7-len(m.group(1))
      # several methods, first one is to use:
      while(wikidepths[-1]>=newwikidepth): wikidepths.pop(); parents.pop()
      wikidepths=wikidepths+[newwikidepth]
      parent=c.appendNode(parents[-1], title,{'header':None})
      parents=parents+[parent]
  if (txt): c.appendNode(parents[-1],txt,{'textbody':None})
  ki.setMCache(meta)

def wiki2th(w,dst):
  import os
  import os.path
  import Thawab.core
  import shutil
  n=os.path.basename(w)
  if n.endswith('.txt'): n=n[:-4]+".ki"
  th=Thawab.core.ThawabMan(os.path.expanduser('~/.thawab'))
  ki=th.mktemp()
  wiki=open(w,"rt").read().decode('utf-8').splitlines()
  c=ki.seek(-1,-1)
  importFromWiki(c,wiki)
  c.flush()
  o=ki.uri
  del ki
  shutil.move(o,os.path.join(dst,n))

