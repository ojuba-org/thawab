#! /usr/bin/python3
# -*- coding: UTF-8 -*-
import os, os.path, Thawab.core
th=Thawab.core.ThawabMan()
th.searchEngine.reindexAll()
# th.loadMeta() # to detect new files and add them ..etc.
meta=th.getMeta()
print(meta.getUriList())
th.searchEngine.reindexKitab('/home/alsadi/.thawab/db/uthaymine.ki')

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
#for i in th.searchEngine.queryIndex('إنشاء'.decode('utf-8')): print i['title']
#for i in th.searchEngine.queryIndex('إنشاء kitab:pyqt4'.decode('utf-8')): print i['title']
#for i in th.searchEngine.queryIndex('إنشاء kitab:test'.decode('utf-8')): print i['title']
