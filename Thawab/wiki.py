# -*- coding: utf-8 -*-
"""
The core classes of thawab
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

####################################
header_re=re.compile(r'^\s*(=+)\s*(.+?)\s*\1\s*$')
def wiki2th(ki, wiki):
  """import a wiki-like into a thawab"""
  txt=""
  parents=[ki.root]
  wikidepths=[0]
  title=None
  for l in wiki:
    l=l.decode('utf-8')
    m=header_re.match(l)
    if not m:
      # textbody line: add the line to accumelated textbody variable
      txt+=l
    else:
      # new header:
      # add the accumelated textbody of a previous header (if exists) to the Kitab 
      if txt and title:
        ki.appendToCurrent(parents[-1], txt, {'textbody':None})
      # elif txt and not title: pass # it's leading noise, as title can't be empty because of + in the RE
      # reset the accumelated textbody
      txt=""
      # now get the title of matched by RE
      title=m.group(2)
      newwikidepth=7-len(m.group(1))
      # several methods, first one is to use:
      while(wikidepths[-1]>=newwikidepth): wikidepths.pop(); parents.pop()
      wikidepths=wikidepths+[newwikidepth]
      parent=ki.appendToCurrent(parents[-1], title,{'header':None})
      parents=parents+[parent]
  if (txt): ki.appendToCurrent(parents[-1],txt,{'textbody':None})

