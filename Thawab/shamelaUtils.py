# -*- coding: UTF-8 -*-
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
import bisect

from subprocess import Popen,PIPE
from itertools import groupby,imap
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
no_w_re=re.compile(ur'[^A-Za-zابتثجحخدذرزسشصضطظعغفقكلمنهوي\s]')
# one to one transformations that does not change chars order
sh_digits_to_spaces_tb={
  48:32, 49:32, 50:32, 51:32, 52:32,
  53:32, 54:32, 55:32, 56:32, 57:32
}

sh_normalize_tb={
65: 97, 66: 98, 67: 99, 68: 100, 69: 101, 70: 102, 71: 103, 72: 104, 73: 105, 74: 106, 75: 107, 76: 108, 77: 109, 78: 110, 79: 111, 80: 112, 81: 113, 82: 114, 83: 115, 84: 116, 85: 117, 86: 118, 87: 119, 88: 120, 89: 121, 90: 122,
1569: 1575, 1570: 1575, 1571: 1575, 1572: 1575, 1573: 1575, 1574: 1575, 1577: 1607,  1609: 1575, 
8: 32, 1600:32, 1632: 48, 1633: 49, 1634: 50, 1635: 51, 1636: 52, 1637: 53, 1638: 54, 1639: 55, 1640: 56, 1641: 57, 1642:37, 1643:46
}
# TODO: remove unused variables and methods

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
    self.tables=filter(lambda t: not t.isdigit(), self.tables)
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
      if l:
        try: self.c.execute(l)
        except: print l; raise

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

  def authorByID(self, authno, main_tb={}):
    # TODO: use authno to search shamela specific database
    a,y='_unset',0
    if main_tb:
      a=makeId(main_tb.get('auth',''))
      y=main_tb.get('higrid',0)
      if not y: y=main_tb.get('ad',0)
      if isinstance(y,basestring) and y.isdigit():
        y=int(y)
      else:
        m=digits_re.search(unicode(y))
        if m: y=int(m.group(0))
        else: y=0
    return a,y

  def classificationByBookId(self, bkid):
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
      r=self.c.execute('SELECT bk, shortname, cat, betaka, inf, bkord, authno, higrid, ad, islamshort, is_tafseer, is_sharh FROM main WHERE bkid=?', (bkid,)).fetchone()
      if not r: m=None
      else:
        r=dict(r)
        m={
          "repo":"_user", "lang":"ar",
          "version":"0."+str(bkid), "releaseMajor":"0", "releaseMinor":"0",
          'originalKitab':None, 'originalVersion':None,
        }
        m['kitab']=makeId(r['bk'])
        m['author'],m['year']=self.authorByID(r['authno'], r)
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
    self.suffix=''

  def overlaps_with(self,b):
    return b.end>self.start and self.end>b.start

  def __cmp__(self, b):
    return cmp(self.start,b.start)

def _fixHeadBounds(pg_txt, found):
  for i,f in enumerate(found):
    if f.fuzzy>=4:
      # then the heading is part of some text
      f.end=f.start
      f.suffix=u'\u2026'
      if f.fuzzy>=7:
        #then move f.start to the last \n 
        f.end=max(pg_txt[:f.end].rfind('\n'),0)
      if i>0:
        f.end=max(f.end,found[i-1].end)
      f.start=min(f.start, f.end)

def shamelaImport(cursor, sh, bkid):
  """
  import a ShamelaSqlite book as thawab kitab object, where
    * ki - an empty thawab kitab object
    * sh - ShamelaSqlite object
    * bkid - the id of the shamela book to be imported
  this function returns the cached meta dictionary
  """
  ki=cursor.ki
  # NOTE: page id refers to the number used as id in shamela not thawab
  c=sh.c
  # step 1: import meta
  meta=sh.getBookMeta(bkid)
  ki.setMCache(meta)
  # step 2: prepare topics hashed by page_id
  r=c.execute("SELECT id,tit,lvl FROM t%d ORDER BY id,sub" % bkid).fetchall()
  # NOTE: we only need page_id,title and depth, sub is only used to sort them
  toc_ls=filter(lambda i: i[2] and i[1], [list(i) for i in r])
  if not toc_ls: raise TypeError # no text in the book
  toc_hash=map(lambda i: (i[1][0],i[0]),enumerate(toc_ls))
  # toc_hash.sort(lambda a,b: cmp(a[0],b[0])) # FIXME: this is not needed!
  toc_hash=dict(map(lambda j: (j[0],map(lambda k:k[1], j[1])), groupby(toc_hash,lambda i: i[0])))
  # NOTE: toc_hash[pg_id] holds list of indexes in toc_ls
  found=[]
  parents=[ki.root]
  depths=[-1] # -1 is used to indicate depth or level as shamela could use 0
  last=u''
  started=False
  rm_fz4_re=re.compile(ur'(?:[^\w\n]|[_ـ])',re.M | re.U) # [\W_ـ] without \n
  rm_fz7_re=re.compile(ur'(?:[^\w\n]|[\d_ـ])',re.M | re.U) # [\W\d_ـ] without \n

  def _shamelaFindHeadings(page_txt, page_id, d, h, headings_re, heading_ix,j, fuzzy):
    # fuzzy is saved because it could be used later to figure whither to add newline or to move start point
    for m in headings_re.finditer(page_txt): # 
      candidate=_foundShHeadingMatchItem(m.start(), m.end(), h, d, fuzzy)
      ii = bisect.bisect_left(found, candidate) # only check for overlaps in found[ii:]
      # skip matches that overlaps with previous headings
      if any(imap(lambda mi: mi.overlaps_with(candidate),found[ii:])): continue
      bisect.insort(found, candidate) # add the candidate to the found list
      toc_hash[page_id][j]=None
      return True
    return False

  def _shamelaFindExactHeadings(page_txt, page_id, f, d, heading, heading_ix,j, fuzzy):
    shift=0
    s= f % page_txt
    h= f % heading
    #print "*** page:", s
    #print "*** h:", page_id, heading_ix, fuzzy, "[%s]" % h.encode('utf-8')
    l=len(heading)
    while(True):
      i=s.find(h)
      if i>=0:
        # print "found"
        candidate=_foundShHeadingMatchItem(i+shift, i+shift+l, h, d, fuzzy)
        ii = bisect.bisect_left(found, candidate) # only check for overlaps in found[ii:]
        # skip matches that overlaps with previous headings
        if not any(imap(lambda mi: mi.overlaps_with(candidate),found[ii:])):
          bisect.insort(found, candidate) # add the candidate to the found list
          toc_hash[page_id][j]=None
          return True
        # skip to i+l
        s=s[i+l:]
        shift+=i+l
      # not found:
      return False
    return False

  def _shamelaHeadings(page_txt, page_id):
    l=toc_hash.get(page_id,[])
    if not l: return
    txt=None
    txt_no_d=None
    # for each heading
    for j,ix in enumerate(l):
      h,d=toc_ls[ix][1:3]
      # search for entire line matches (exact, then only letters and digits then only letters)
      # search for leading matches (exact, then only letters and digits then only letters)
      # search for matches anywhere (exact, then only letters and digits then only letters)
      if _shamelaFindExactHeadings(page_txt, page_id, "\n%s\n", d, h, ix,j, 1): continue
      if not txt: txt=no_w_re.sub(' ', page_txt.translate(sh_normalize_tb))
      h_p=no_w_re.sub(' ', h.translate(sh_normalize_tb)).strip()
      if h_p: # if normalized h_p is not empty
        # NOTE: no need for map h_p on re.escape() because it does not contain special chars
        h_re_entire_line=re.compile(ur"^\s*%s\s*$" % ur" *".join(list(h_p)), re.M)
        if _shamelaFindHeadings(txt, page_id, d, h, h_re_entire_line, ix, j, 2): continue

      if not txt_no_d: txt_no_d=txt.translate(sh_digits_to_spaces_tb)
      h_p_no_d=h_p.translate(sh_digits_to_spaces_tb).strip()
      if h_p_no_d:
        h_re_entire_line_no_d=re.compile(ur"^\s*%s\s*$" % ur" *".join(list(h_p_no_d)), re.M)
        if _shamelaFindHeadings(txt_no_d, page_id, d, h, h_re_entire_line_no_d, ix, j, 3): continue

      # at the beginning of the line
      if _shamelaFindExactHeadings(page_txt, page_id, "\n%s", d, h, ix,j, 4): continue
      if h_p:
        h_re_line_start=re.compile(ur"^\s*%s\s*" % ur" *".join(list(h_p)), re.M)
        if _shamelaFindHeadings(txt, page_id, d, h, h_re_line_start, ix, j, 5): continue
      if h_p_no_d:
        h_re_line_start_no_d=re.compile(ur"^\s*%s\s*" % ur" *".join(list(h_p_no_d)), re.M)
        if _shamelaFindHeadings(txt_no_d, page_id, d, h, h_re_line_start_no_d, ix, j, 6): continue
      # any where in the line
      if _shamelaFindExactHeadings(page_txt, page_id, "%s", d, h, ix,j, 7): continue
      if h_p:
        h_re_any_ware=re.compile(ur"\s*%s\s*" % ur" *".join(list(h_p)), re.M)
        if _shamelaFindHeadings(txt, page_id, d, h, h_re_any_ware, ix, j, 8): continue
      if h_p_no_d:
        h_re_any_ware_no_d=re.compile(ur"\s*%s\s*" % ur" *".join(list(h_p_no_d)), re.M)
        if _shamelaFindHeadings(txt_no_d, page_id, d, h, h_re_any_ware, ix, j, 9): continue
      # No head found, add it just after last one
      if found:
        last_end=found[-1].end
        try: last_end+=page_txt[last_end:].index('\n')+1
        except ValueError: last_end=len(page_txt)
      else: last_end=0
      candidate=_foundShHeadingMatchItem(last_end, last_end, h, d, 0)
      bisect.insort(found, candidate) # add the candidate to the found list
    del toc_hash[page_id]
    return

  # step 3: walk through pages, accumelating conents  
  # NOTE: in some books id need not be unique
  for r in c.execute("SELECT id,nass,part,page,hno,sora,aya,na FROM b%d ORDER BY id" % bkid):
    pg_txt=r['nass'].translate(dos2unix_tb)
    pg_id=r['id']
    # TODO: set the value of header tag to be a unique reference
    # TODO: keep part,page,hno,sora,aya,na somewhere in the imported document
    # TODO: add special handling for hadeeth number and tafseer info
    found=[]
    # step 4: for each page content try to find all headings
    _shamelaHeadings(pg_txt, pg_id)
    # now we got all headings in found
    # step 5: add the found headings and its content
    # splitting page text pg_txt into [:f0.start] [f0.end:f1.start] [f1.end:f2.start]...[fn.end:]
    # step 5.1: add [:f0.start] to the last heading contents and push it
    if not found: last+=pg_txt; continue
    _fixHeadBounds(pg_txt, found)
    if started: cursor.appendNode(parents[-1], last+pg_txt[:found[0].start], {'textbody':None})
    # step 5.2: same for all rest segments [f0.end:f1.start],[f1.end:f2.start]...[f(n-1).end:fn.start]
    for i,f in enumerate(found[:-1]):
      while(depths[-1]>=f.depth): depths.pop(); parents.pop()
      started=True
      h_tags={'header':None} # FIXME: replace None with a unique _aXYZ identifier
      if f.fuzzy==0: h_tags[u'request.fix']=u'shamela import error: missing head'
      parent=cursor.appendNode(parents[-1], f.txt+f.suffix, h_tags)
      parents.append(parent)
      depths.append(f.depth)
      parent=cursor.appendNode(parent, pg_txt[f.end:found[i+1].start], {'textbody':None})
    # step 5.3: save [fn.end:] as last heading
    f=found[-1]
    while(depths[-1]>=f.depth): depths.pop(); parents.pop()
    h_tags={'header':None} # FIXME: replace None with a unique _aXYZ identifier
    txt_start=f.end
    if f.fuzzy==0: h_tags[u'request.fix']=u'shamela import error: missing header'
    parent=cursor.appendNode(parents[-1], f.txt+f.suffix,h_tags)
    started=True
    parents.append(parent)
    depths.append(f.depth)
    last=pg_txt[f.end:]+'\n\n'

  if not started: raise TypeError
  if last: cursor.appendNode(parents[-1], last, {'textbody':None})
  # l should be empty because we have managed missing headers
  #l=filter(lambda i: i,toc_hash.values())
  #for j in l: print j
  #print "*** headings left: ",len(l)
  return meta

if __name__ == '__main__':
  # input bok_fn, dst
  th=ThawabMan(os.path.expanduser('~/.thawab'))
  sh=ShamelaSqlite(bok_fn)
  sh.toSqlite()
  for bok_id in sh.getBokIds():
    ki=th.mktemp()
    c=ki.seek(-1,-1)
    meta=shamelaImport(c, cn, bok_id)
    c.flush()
    o=ki.uri
    n=meta['kitab']
    del ki
    shutil.move(o,os.path.join(dst,n))

