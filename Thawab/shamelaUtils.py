# -*- coding: utf-8 -*-
"""
The shamela related tools for thawab
Copyright © 2008-2009, Muayyad Saleh Alsadi <alsadi@ojuba.org>

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
import re
import sqlite3

from subprocess import Popen,PIPE
from meta import MCache

schema={
  'main':"bkid INTEGER, bk TEXT, thwab INTEGER, shortname TEXT, cat INTEGER, betaka TEXT, inf TEXT, bkord INTEGER DEFAULT -1, authno INTEGER DEFAULT 0, auth_death INTEGER DEFAULT 0,islamshort INTEGER DEFAULT 0, is_tafseer INTEGER DEFAULT 0, is_sharh INTEGER DEFAULT 0",
  'men': "id INTEGER, arrname TEXT, isoname TEXT, dispname TEXT",
  'shorts': "bk INTEGER, ramz TEXT, nass TEXT",
  'mendetail': "spid INTEGER PRIMARY KEY, manid INTEGER, bk INTEGER, id INTEGER, talween TEXT",
  'shrooh': "matn INTEGER, matnid INTEGER, sharh INTEGER, sharhid INTEGER",
  'cat':"id INTEGER PRIMARY KEY, name Text, catord INTEGER, lvl INTEGER",
  'book':"id, nass TEXT, part INTEGER DEFAULT 0, page INTEGER DEFAULT 0, hno INTEGER DEFAULT 0, sora INTEGER DEFAULT 0, aya INTEGER DEFAULT 0, na INTEGER DEFAULT 0",
  'toc': "id INTEGER, tit TEXT, lvl INTEGER DEFAULT 1, sub INTEGER DEFAULT 0"
}
schema_index={
  'main':"CREATE INDEX MainBkIdIndex on main (bkid);",
  'men': "CREATE INDEX MenIdIndex on men (id); CREATE INDEX MenIsoNameIndex on men (isoname);",
  'shorts': "CREATE INDEX ShortsIndex on shorts (bk,ramz);",
  'mendetail': "CREATE INDEX MenDetailSpIdIndex on mendetail (spid);",
  'shrooh': "CREATE INDEX ShroohIndex on shrooh (matn,matnid);",
  'book':"CREATE INDEX Book%(table)sIdIndex on %(table)s (id);",
  'toc': "CREATE INDEX Toc%(table)sIdIndex on %(table)s (id);"
}
hashlen=32 # must be divisible by 4
# some mark to know how and where to cut
mark="-- CUT HERE STUB (%s) BUTS EREH TUC --\n" % os.urandom(hashlen*3/4).encode('base64')[:hashlen]

table_cols=dict(map(lambda tb: (tb,map(lambda i: i.split()[0],schema[tb].split(','))), schema.keys()))
table_col_defs=dict(map(lambda tb: (tb,dict(map(lambda i: (i.strip().split()[0],i.strip()),schema[tb].split(',')))), schema.keys()))


# transformations
dos2unix_tb={13: 10}
normalize_tb={
65: 97, 66: 98, 67: 99, 68: 100, 69: 101, 70: 102, 71: 103, 72: 104, 73: 105, 74: 106, 75: 107, 76: 108, 77: 109, 78: 110, 79: 111, 80: 112, 81: 113, 82: 114, 83: 115, 84: 116, 85: 117, 86: 118, 87: 119, 88: 120, 89: 121, 90: 122,
1600: None, 1569: 1575, 1570: 1575, 1571: 1575, 1572: 1575, 1573: 1575, 1574: 1575, 1577: 1607, 1611: None, 1612: None, 1613: None, 1614: None, 1615: None, 1616: None, 1617: None, 1618: None, 1609: 1575}
spaces='\t\n\r\f\v'
spaces_d=dict(map(lambda s: (ord(s),32),list(spaces)))

schema_fix_del=re.compile('\(\d+\)') # match digits in parenthesis (after types) to be removed
schema_fix_text=re.compile('Memo/Hyperlink',re.I)
schema_fix_int=re.compile('(Boolean|Byte|Byte|Numeric|Replication ID|(\w+ )?Integer)',re.I)
sqlite_cols_re=re.compile("\((.*)\)",re.M | re.S)
no_sql_comments=re.compile('^--.*$',re.M)

class ShamelaSqlite(object):
  def __init__(self, bok_fn, cn=None, progress=None, progress_data=None):
    """import the bok file into sqlite"""
    self.progress=progress
    self.progress_data=progress_data
    self.tables=None
    self.bok_fn=bok_fn
    self.version,self.tb,self.bkids=self.identify()
    # note: the difference between tb and self.tables that tables are left as reported by mdbtoolds while tb are lower-cased
    self.cn=cn or sqlite3.connect(':memory:', isolation_level=None)
    self.c=self.cn.cursor()
    self.imported_tables=[]

  def identify(self):
    tables=self.getTables() # Note: would raise OSError or TypeError
    if len(tables)==0: raise TypeError
    tables.sort()
    tb=dict(map(lambda s: (s.lower(),s), tables))
    if 'book' in tables and 'title' in tables: return (2,tb,[])
    bkid=map(lambda i:int(i[1:]),filter(lambda i: i[0]=='b' and i[1:].isdigit(),tables))
    bkid.sort()
    return (3,tb,bkid)

  def getTables(self):
    if self.tables: return self.tables
    try: p=Popen(['mdb-tables', '-1',self.bok_fn], 0, stdout=PIPE)
    except OSError: raise
    try: self.tables=p.communicate()[0].strip().split('\n')
    except OSError: raise
    r=p.returncode; del p
    if r!=0: raise TypeError
    return self.tables

  def __shamela3_fix_insert(self, sql_cmd, prefix="OR IGNORE INTO tmp_"):
    """Internal function used by importTable"""
    if prefix and sql_cmd[0].startswith('INSERT INTO '): sql_cmd[0]='INSERT INTO '+prefix+sql_cmd[0][12:]
    sql=''.join(sql_cmd)
    #print sql
    self.c.execute(sql)

  def __schemaGetCols(self, r):
    """used internally by importTableSchema"""
    m=sqlite_cols_re.search( no_sql_comments.sub('',r) )
    if not m: return []
    return map(lambda i: i.split()[0], m.group(1).split(','))

  def importTableSchema(self, Tb, tb, is_tmp=False,prefix='tmp_'):
    """create schema for table"""
    if is_tmp: temp='temp'
    else: temp=''
    pipe=Popen(['mdb-schema', '-S','-T', Tb, self.bok_fn], 0, stdout=PIPE,env={'MDB_JET3_CHARSET':'cp1256'})
    r=pipe.communicate()[0]
    if pipe.returncode!=0: raise TypeError
    sql=schema_fix_text.sub('TEXT',schema_fix_int.sub('INETEGER',schema_fix_del.sub('',r))).lower()
    sql=sql.replace('create table ',' '.join(('create ',temp,' table ',prefix,)))
    sql=sql.replace('drop table ','drop table if exists '+prefix)
    cols=self.__schemaGetCols(sql)
    if table_cols.has_key(tb):
      missing=filter(lambda i: not i in cols,table_cols[tb])
      missing_def=u', '.join(map(lambda i: table_col_defs[tb][i],missing))
    else:
      missing=[]
      missing_def=u''
    if missing_def: sql=sql.replace('\n)',','+missing_def+'\n)')
    sql+=schema_index.get(tb,'') % {'table': Tb.lower()}
    sql_l=no_sql_comments.sub('',sql).split(';')
    for l in sql_l:
      l=l.strip()
      if l: self.c.execute(l)

  def importTable(self, Tb, tb, tb_prefix=None, is_tmp=False, is_ignore=False, is_replace=False):
    """
    import a table where:
  * Tb is the case-sesitive table name found reported in mdbtools.
  * tb is the name in our standard schema, usually tb=Tb.lower() except for book and toc where its Tb is b${bok_id}, t${bok_id}
  * tb_prefix a prefix added to tb [default is tmp_ if is_tmp otherwise it's '']
     """
    tb_prefix=is_tmp and 'tmp_' or ''
    if Tb in self.imported_tables: return
    self.importTableSchema(Tb, tb, is_tmp, tb_prefix)
    pipe=Popen(['mdb-export', '-R',';\n'+mark,'-I', self.bok_fn, Tb], 0, stdout=PIPE,env={'MDB_JET3_CHARSET':'cp1256'})
    sql_cmd=[]
    prefix=""
    if is_ignore: prefix="OR IGNORE INTO "
    elif is_replace: prefix="OR REPLACE INTO "
    prefix+=tb_prefix
    for l in pipe.stdout:
      if l==mark: self.__shamela3_fix_insert(sql_cmd,prefix); sql_cmd=[]
      else: sql_cmd.append(l)
    if len(sql_cmd): self.__shamela3_fix_insert(sql_cmd,prefix); sql_cmd=[]
    if pipe.returncode!=0: raise TypeError
    del pipe
    self.imported_tables.append(Tb)

  def toSqlite(self, in_transaction=True, bkids=None):
    if in_transaction: self.c.execute('BEGIN TRANSACTION')
    tables=self.getTables()
    is_special=lambda t: (t.lower().startswith('t') or t.lower().startswith('b')) and t[1:].isdigit()
    is_not_special=lambda t: not is_special(t)
    s_tables=filter(is_special, tables)
    g_tables=filter(is_not_special, tables)
    if bkids:
      # filter bkids in s_tables
      s_tables=filter(lambda t: int(t[1:]) in bkids, s_tables)
    progress_delta=1.0/(len(s_tables)+len(g_tables))*100.0
    progress=0.0
    for t in g_tables:
      if self.progress: self.progress("importing table [%s]" % t,progress, self.progress_data)
      progress+=progress_delta
      self.importTable(t, t.lower())
    for t in s_tables:
      if self.progress: self.progress("importing table [%s]" % t,progress, self.progress_data)
      progress+=progress_delta
      if t.lower().startswith('t'):
        self.importTable(t, 'toc')
      else:
        self.importTable(t, 'book')
    progress=100.0
    if self.progress: self.progress("finished, committing ...",progress, self.progress_data)
    if in_transaction: self.c.execute('END TRANSACTION')

if __name__ == '__main__':
  # input bok_fn, dst
  th=ThawabMan(os.path.expanduser('~/.thawab'))
  sh=ShamelaSqlite(bok_fn)
  sh.toSqlite()
  for bok_id in sh.getBokIds():
    ki=th.mktemp()
    ki.seek(-1,-1)
    meta=shamelaImport(ki, cn, bok_id)
    ki.flush()
    o=ki.uri
    n=meta['kitab']
    del ki
    shutil.move(o,os.path.join(dst,n))

