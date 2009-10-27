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
from itertools import groupby
from meta import MCache, prettyId, makeId

schema={
  'main':"bkid INTEGER, bk TEXT, shortname TEXT, cat INTEGER, betaka TEXT, inf TEXT, bkord INTEGER DEFAULT -1, authno INTEGER DEFAULT 0, auth TEXT, authinfo TEXT, higrid INTEGER DEFAULT 0, ad INTEGER DEFAULT 0, islamshort INTEGER DEFAULT 0, is_tafseer INTEGER DEFAULT 0, is_sharh INTEGER DEFAULT 0",
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

digits_re=re.compile(r'\d+')

class ShamelaSqlite(object):
  def __init__(self, bok_fn, cn=None, progress=None, progress_data=None):
    """import the bok file into sqlite"""
    self.progress=progress
    self.progress_data=progress_data
    self.tables=None
    self.bok_fn=bok_fn
    self.__bkids=None
    self.__commentaries=None
    self.version,self.tb,self.bkids=self.identify()
    # note: the difference between tb and self.tables that tables are left as reported by mdbtoolds while tb are lower-cased
    self.cn=cn or sqlite3.connect(':memory:', isolation_level=None)
    self.cn.row_factory=sqlite3.Row
    self.c=self.cn.cursor()
    self.imported_tables=[]
    self.__meta_by_bkid={}

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
    print "waiting child process...",pipe.wait() # TODO: why is this needed
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
    self.__getCommentariesHash()

  def __getCommentariesHash(self):
    if self.__commentaries!=None: return self.__commentaries
    self.__commentaries={}
    for a in self.c.execute('SELECT DISTINCT matn, sharh FROM shrooh'):
      try: r=(int(a[0]),int(a[1])) # fix that some books got string bkids not integer
      except ValueError: continue # skip non integer book ids
      if self.__commentaries.has_key(r[0]):
        self.__commentaries[r[0]].append(r[1])
      else: self.__commentaries[r[0]]=[r[1]]
    for i in self.getBookIds():
      if not self.__commentaries.has_key(i): self.__commentaries[i]=[]
    return self.__commentaries

  def authorByID(authno, main={}):
    # TODO: use authno to search shamela specific database
    a,y='_unset',0
    if main:
      a=makeId(main.get('auth'],''))
      y=makeId(main.get('higrid'],0))
      if not y: y=makeId(main.get('ad'],0))
      try: y=int(y)
      except TypeError:
        m=digits_re.search(unicode(y))
        if m: y=int(m.group(0))
    return a,y

  def classificationByBookId(bkid):
    return '_unset'

  def getBookIds(self):
    if self.__bkids!=None: return self.__bkids
    r=self.c.execute('SELECT bkid FROM main')
    self.__bkids=map(lambda a: a[0],r.fetchall() or [])
    if self.__commentaries!=None:
      # sort to make sure we import the book before its commentary
      self.__bkids.sort(lambda a,b: (int(a in self.__commentaries.get(b,[]))<<1) - 1)
    return self.__bkids

  def getBookMeta(self, bkid):
    if self.__meta_by_bkid.has_key(bkid): return self.__meta_by_bkid[bkid]
    else:
      r=self.c.execute('SELECT bk, shortname, cat, betaka, inf, bkord, authno, auth_death, islamshort, is_tafseer, is_sharh FROM main WHERE bkid=?', (bkid,)).fetchone()
      if not r: m=None
      else:
        r=dict(r)
        m={
          "repo":"_user", "lang":"ar",
          "version":"0."+str(bkid), "releaseMajor":"0", "releaseMinor":"0",
        }
        m['kitab']=makeId(r['bk'])
        m['author'],m['year']=self.authorByID(r['authno'], main=r)
        m['classification']=self.classificationByBookId(bkid)
        #"originalAuthor", "originalYear", "originalKitab", "originalVersion"
      self.__meta_by_bkid[bkid]=m
      return m

class _foundShHeadingMatchItem():
  def __init__(self, start, end=-1, txt='', depth=-1, fuzzy=-1):
    self.start=start
    self.end=end
    self.txt=txt
    self.depth=depth
    self.fuzzy=fuzzy

  def overlaps_with(b):
    return b.end>self.start and self.end>b.start

  def __cmp__(self, b):
    return cmp(self.start,b.start)

def shamelaImport(ki, sh, bkid):
  """
  import a ShamelaSqlite book as thawab kitab object, where
    * ki - an empty thawab kitab object
    * sh - ShamelaSqlite object
    * bkid - the id of the shamela book to be imported
  this function returns the cached meta dictionary
  """
  # currently this is dummy importing, that does not process the text
  c=sh.c
  # step 1: import meta
  meta=sh.getBookMeta(bkid)
  # step 2: prepare topics hashed by page_id
  r=c.execute("SELECT id FROM b%d ORDER BY id DESC LIMIT 1" % bkid).fetchone()
  if r: max_id=r[0]
  else: raise TypeError # no text in the book
  r=c.execute("SELECT rowid,id,tit,lvl,sub FROM t%d ORDER BY id,sub" % bkid).fetchall()
  toc=map(lambda a: list(a).append(max_id+1),r) # TODO: what are the needed items ?
  toc.append([-1,max_id+1,'',0,0,max_id+1])
  toc_hash=map(lambda j: (j[0],list(j[1])),list(groupby(toc,lambda i: i[1])))
  toc_ids=map(lambda j: j[0],toc_hash) # TODO: is this needed ?
  toc_hash=dict(toc_hash)
  found=[]
  parents=[ki.root]
  depths=[-1] # -1 is used to indicate depth or level as shamela could use 0
  last=u''
  started=False

  def _shamelaHeadings(txt, page_id, fuzzy=0):
    n=0
    if not toc_hash.get(page_id,{}): return 0
    if fuzzy=0:
      for i in toc_hash[page_id]:
        h_re="^%s$" % re.escape(i)
        for m in re.finditer(h_re,txt,re.M):
          candidate=_foundShHeadingMatchItem(m.start(), m.end(), i, toc_hash[i][SH_DEPTH], fuzzy)
          ii = bisect.bisect_left(found, candidate) # only check for overlaps in found[ii:]
          # skip matches that overlaps with previous headings
          if any(imap(lambda mi: mi.overlaps_with(candidate),found[ii:])): continue
          n+=1
          bisect.insort(found, candidate) # add the candidate to the found list
          del toc_hash[page_id][i]
          break;
    else: raise TypeError # invalid fuzzy
    return n
    

  for i,t in range(len(toc)-1): toc[i][5]=toc[i+1][1]
  # step 3: walk through pages, accumelating conents  
  # NOTE: in some books id need not be unique
  for r in c.execute("SELECT id,nass,part,page,hno,sora,aya,na FROM b%d ORDER BY id" % page_id):
    pg_txt=r['nass']
    pg_id=r['id']
    found=[]
    # step 4: for each page content try to find all headings
    # step 4.1.1: search for exact entire line matches ie. ^<PAT>$ in the current page and push match start and end, and pop the matched item from toc_hash (ie. delete them)
    _shamelaHeadings(pg_txt, pg_id, 0)
    # step 4.1.2: as 4.1.1 but with leading matches ie. ^<PAT>
    # step 4.1.3: as 4.1.1 but in-line <PAT> without ^ nor $
    # step 4.2.1-3: same as 4.1.1-3 but with s/[\W_]//;
    # step 4.3.1-3: same as 4.1.1-3 but with s/[\W\d_]//;
    # TODO: implement 4.1.x-4.2.x
    # NOTE: all steps works on tr/ \t/ /s;
    # NOTE: each step in 4.x.y should be inside a loop over unfinished headings because all topics could be founded in 4.1.1 and poped and all the rest steps are skiped
    # TODO: how to mark start and end in original content even after offset change after s// and tr// ops ?
    # now we got all headings in found
    # step 5: add the found headings and its content
    # splitting page text pg_txt into [:f0.start] [f0.end:f1.start] [f1.end:f2.start]...[fn.end:]
    # step 5.1: add [:f0.start] to the last heading contents and push it
    if not found: last+=pg_txt; continue
    if started: ki.appendToCurrent(parents[-1], last+pg_txt[:found[0].start], {'textbody':None})
    # step 5.2: same for all rest segments [f0.end:f1.start],[f1.end:f2.start]...[f(n-1).end:fn.start]
    for i,f in enumerate(found[:-1]):
      while(depths[-1]>=f.depth): depths.pop(); parents.pop()
      started=True
      parent=ki.appendToCurrent(parents[-1], f.txt,{'header':None})
      parents.append(parent)
      depths.append(f.depth)
      parent=ki.appendToCurrent(parent, pg_txt[f.end:found[i+1].start], {'textbody':None})
    # step 5.3: save [fn.end:] as last heading
    f=found[-1]
    while(depths[-1]>=f.depth): depths.pop(); parents.pop()
    parent=ki.appendToCurrent(parents[-1], f.txt,{'header':None})
    started=True
    parents.append(parent)
    last=pg_txt[f.end:]
    #s=s.replace('\t','').replace(' ','')
    #h=r"[\W\s]*?".join(map(lambda i: re.escape(i),list(s)))
    #h_re=re.compile(h, re.M)

  return meta

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

