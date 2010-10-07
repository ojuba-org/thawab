# -*- coding: UTF-8 -*-
"""
Platform specific routines of thawab
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
import sys, os, os.path
from glob import glob

if sys.platform == 'win32':

  def get_drives():
    return filter(lambda j: os.path.exists(j), [chr(i)+':\\' for i in range(67,91)])

  try: from winpaths import get_appdata as application_data
  except ImportError:
    try: from winshell import application_data
    except ImportError:
      try:
        import win32com.shell as shell
        def application_data():
          return shell.SHGetFolderPath(0, 26, 0, 0)
      except ImportError:
        application_data=None
  if application_data:
    app_data=application_data()
    th_conf=os.path.join(app_data,u"thawab","conf","main.conf")
  else:
    app_data=u"C:\\"
    th_conf=u"C:\\thawab.conf"

else:
  app_data=u"/usr/share/"
  application_data=None
  def get_drives(): return []
  th_conf=os.path.expanduser('~/.thawab/conf/main.conf')

def guess_prefixes():
  l=[]
  ed=os.path.join(os.path.dirname(sys.argv[0]),u'thawab-data')
  ed_1st=False
  if os.path.isdir(ed) and os.access(ed, os.W_OK): l.append(ed); ed_1st=True
  if sys.platform == 'win32':
    l.append(os.path.join(app_data,'thawab'))
    if not ed_1st: l.append(ed)
    l.extend([os.path.join(d,'thawab-data') for d in get_drives()])
  else:
    l.append(os.path.expanduser('~/.thawab'))
    if not ed_1st: l.append(ed)
    l.append(u'/usr/local/share/thawab')
    l.append(u'/usr/share/thawab')
  return l


