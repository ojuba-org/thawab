#! /usr/bin/python
# -*- coding: utf-8 -*-
import os
import os.path
import Thawab.core

th=Thawab.core.ThawabMan(os.path.expanduser('~/.thawab'))
th.loadMCache()
print th.getManagedList()
ki=th.mktemp()
wiki_filename="samples/test.txt"
wiki=open(wiki_filename,"rt")
ki.seek(-1,-1)
Thawab.core.wiki2th(ki,wiki)
ki.flush()

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
