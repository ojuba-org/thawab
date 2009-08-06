#! /usr/bin/python
# -*- coding: utf-8 -*-
import os
import os.path
import Thawab.core
th=Thawab.core.ThawabMan(os.path.expanduser('~/.thawab'))
# th.loadMeta() # to detect new files and add them ..etc.
meta=th.getMeta()
print meta.get_uri_list()

## export to xml
#from cStringIO import StringIO
#s=StringIO()
#ki=Thawab.core.Kitab('/home/alsadi/.thawab/tmp/THAWAB_xqkca0.ki3001')
#n=ki.root.toXml(s)
#print s.getvalue()

## export to HTML or wiki
#import Thawab.core
#ki=Thawab.core.Kitab('/home/alsadi/.thawab/tmp/THAWAB_xqkca0.ki3001')
#s=ki.root.toHTML()
#print s

##searching the index
#for i in th.queryIndex('إنشاء'.decode('utf-8')): print i['title']
#for i in th.queryIndex('إنشاء kitabName:pyqt4'.decode('utf-8')): print i['title']
#for i in th.queryIndex('إنشاء kitabName:test'.decode('utf-8')): print i['title']
