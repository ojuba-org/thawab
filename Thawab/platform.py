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
   if application_data: th_conf=os.path.join(application_data(),u"thawab","conf","main.conf")
   else: th_conf=u"C:\\thawab.conf"

else:
  application_data=None
  def get_drives(): return []
  th_conf=os.path.expanduser('~/.thawab/conf/main.conf')

