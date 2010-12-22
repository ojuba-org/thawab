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
from okasha.utils import cmp_bisect_right

from subprocess import Popen,PIPE
from itertools import groupby,imap
from meta import MCache, prettyId, makeId

schema={
  'main':"bkid INTEGER, bk TEXT, shortname TEXT, cat INTEGER, betaka TEXT, inf TEXT, bkord INTEGER DEFAULT -1, authno INTEGER DEFAULT 0, auth TEXT, authinfo TEXT, higrid INTEGER DEFAULT 0, ad INTEGER DEFAULT 0, islamshort INTEGER DEFAULT 0, blnk TEXT",
  'men': "id INTEGER, arrname TEXT, isoname TEXT, dispname TEXT",
  'shorts': "bk INTEGER, ramz TEXT, nass TEXT",
  'mendetail': "spid INTEGER PRIMARY KEY, manid INTEGER, bk INTEGER, id INTEGER, talween TEXT",
  'shrooh': "matn INTEGER, matnid INTEGER, sharh INTEGER, sharhid INTEGER, PRIMARY KEY (sharh, sharhid)",
  'cat':"id INTEGER PRIMARY KEY, name Text, catord INTEGER, lvl INTEGER",
  'book':"id, nass TEXT, part INTEGER DEFAULT 0, page INTEGER DEFAULT 0, hno INTEGER DEFAULT 0, sora INTEGER DEFAULT 0, aya INTEGER DEFAULT 0, na INTEGER DEFAULT 0, blnk TEXT",
  'toc': "id INTEGER, tit TEXT, lvl INTEGER DEFAULT 1, sub INTEGER DEFAULT 0"
}
schema_index={
  'main':"CREATE INDEX MainBkIdIndex on main (bkid);",
  'men': "CREATE INDEX MenIdIndex on men (id); CREATE INDEX MenIsoNameIndex on men (isoname);",
  'shorts': "CREATE INDEX ShortsIndex on shorts (bk,ramz);",
  'mendetail': "CREATE INDEX MenDetailSpIdIndex on mendetail (spid);",
  'shrooh': "CREATE INDEX ShroohIndex on shrooh (sharhid);",
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
shamela_footers_re=re.compile('^(_{4,})$',re.M)
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

# shorts
std_shorts={
  u'A': u'صلى الله عليه وسلم',
  u'B': u'رضي الله عن',
  u'C': u'رحمه الله',
  u'D': u'عز وجل',
  u'E': u'عليه الصلاة و السلام', 
}

footnotes_cnd=[] # candidate, in the form of (footnote_mark, footnote_text) tuples
footnotes=[]
def footer_shift_cb(mi):
  global footnotes_cnd, footnotes
  if footnotes_cnd and footnotes_cnd[0][0]==mi.group(1):
    # int(mi.group(1))
    footnotes.append(footnotes_cnd.pop(0))
    return " ^["+str(len(footnotes))+"]"
  return mi.group(0)


class ShamelaSqlite(object):
  def __init__(self, bok_fn, cn=None, releaseMajor=0, releaseMinor=0, progress=None, progress_args=[], progress_kw={}, progress_dict=None):
    """import the bok file into sqlite"""
    self.releaseMajor = releaseMajor
    self.releaseMinor = releaseMinor
    self.progress = progress
    self.progress_args = progress_args
    self.progress_kw = progress_kw
    self.progress_dict = progress_dict
    self.tables=None
    self.bok_fn=bok_fn
    self.metaById={}
    self._blnk={}
    self.xref={}
    self.encoding_fix_needed=None # True/False or None ie. not yet checked
    self.__bkids=None
    self.__commentaries=None
    self.version,self.tb,self.bkids=self.identify()
    if self.progress_dict==None: self.progress_dict={}
    # note: the difference between tb and self.tables that tables are left as reported by mdbtoolds while tb are lower-cased
    self.cn=cn or sqlite3.connect(':memory:', isolation_level=None)
    self.cn.row_factory=sqlite3.Row
    self.c=self.cn.cursor()
    self.imported_tables=[]
    self.__meta_by_bkid={}

  def set_xref(self, bkid, pg_id, xref):
    if self.xref.has_key(bkid):
      self.xref[bkid].append( (pg_id, xref,) )
    else:
      self.xref[bkid]=[ (pg_id, xref,) ]

  def get_xref(self, bkid, pg_id):
    if self.xref.has_key(bkid):
      i=cmp_bisect_right( lambda a,b: cmp(a[0], b), self.xref[bkid], pg_id)
      if i>0: return self.xref[bkid][i-1][1]
    return None

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
    try: p=Popen(['mdb-tables', '-1',self.bok_fn], 0, stdout=PIPE, env={'MDB_JET3_CHARSET':'cp1256', 'MDB_ICONV':'UTF-8'})
    except OSError: raise
    try: self.tables=p.communicate()[0].replace('\r','').strip().split('\n')
    except OSError: raise
    r=p.returncode; del p
    if r!=0: raise TypeError
    self.tables=filter(lambda t: not t.isdigit(), self.tables)
    return self.tables

  def __shamela3_fix_insert(self, sql_cmd, prefix="OR IGNORE INTO tmp_"):
    """Internal function used by importTable"""
    if prefix and sql_cmd[0].startswith('INSERT INTO '): sql_cmd[0]='INSERT INTO '+prefix+sql_cmd[0][12:]
    sql=''.join(sql_cmd)
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
    pipe=Popen(['mdb-schema', '-S','-T', Tb, self.bok_fn], 0, stdout=PIPE,env={'MDB_JET3_CHARSET':'cp1256', 'MDB_ICONV':'UTF-8'})
    r=pipe.communicate()[0].replace('\r','')
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
    pipe=Popen(['mdb-export', '-R',';\n'+mark,'-I', self.bok_fn, Tb], 0, stdout=PIPE,env={'MDB_JET3_CHARSET':'cp1256', 'MDB_ICONV':'UTF-8'})
    sql_cmd=[]
    prefix=""
    if is_ignore: prefix="OR IGNORE INTO "
    elif is_replace: prefix="OR REPLACE INTO "
    prefix+=tb_prefix
    for l in pipe.stdout:
      l=l.replace('\r','\n')
      # output encoding in mdbtools in windows is cp1256, this is a bug in it
      if self.encoding_fix_needed==None:
        try: l.decode('UTF-8')
        except: self.encoding_fix_needed=True; l=l.decode('cp1256')
        else: self.encoding_fix_needed=False
      elif self.encoding_fix_needed: l=l.decode('cp1256')
      if l==mark: self.__shamela3_fix_insert(sql_cmd,prefix); sql_cmd=[]
      else: sql_cmd.append(l)
    if len(sql_cmd): self.__shamela3_fix_insert(sql_cmd,prefix); sql_cmd=[]
    pipe.wait() # TODO: why is this needed
    if pipe.returncode!=0: raise TypeError
    del pipe
    self.imported_tables.append(Tb)

  def toSqlite(self, in_transaction=True, bkids=None):
    """
    return True if success, or False if canceled
    """
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
      if self.progress_dict.get('cancel', False): return False
      if self.progress: self.progress("importing table [%s]" % t,progress, *self.progress_args, **self.progress_kw)
      progress+=progress_delta
      self.importTable(t, t.lower())
    for t in s_tables:
      if self.progress_dict.get('cancel', False): return False
      if self.progress: self.progress("importing table [%s]" % t,progress, *self.progress_args, **self.progress_kw)
      progress+=progress_delta
      if t.lower().startswith('t'):
        self.importTable(t, 'toc')
      else:
        self.importTable(t, 'book')
    progress=100.0
    if self.progress: self.progress("finished, committing ...",progress, *self.progress_args, **self.progress_kw)
    if in_transaction: self.c.execute('END TRANSACTION')
    self.__getCommentariesHash()
    return True

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
      a=makeId(main_tb.get('auth','') or '')
      y=main_tb.get('higrid',0) or 0
      if not y: y=main_tb.get('ad',0) or 0
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

  def _is_tafseer(self, bkid):
    r=self.c.execute('''SELECT sora, aya FROM b%d WHERE sora>0 and sora <115 and aya>0 LIMIT 1''' % bkid).fetchone()
    return bool(r)

  def _get_matn(self, sharh_bkid):
    r=self.c.execute('''SELECT matn, matnid, sharh, sharhid FROM shrooh WHERE sharh=? LIMIT 1''', (sharh_bkid, ) ).fetchone()
    if not r: return -1
    return int(r['matn'])

  def getBLink(self, bkid):
    if not self._blnk.has_key(bkid):
      r=self.c.execute('SELECT blnk FROM main WHERE bkid=?', (bkid,)).fetchone()
      self._blnk[bkid]=r['blnk']
    return self._blnk[bkid]

  def getBookMeta(self, bkid):
    if self.__meta_by_bkid.has_key(bkid): return self.__meta_by_bkid[bkid]
    else:
      r=self.c.execute('SELECT bk, shortname, cat, betaka, inf, bkord, authno, auth, higrid, ad, islamshort FROM main WHERE bkid=?', (bkid,)).fetchone()
      if not r: m=None
      else:
        r=dict(r)
        # FIXME: make "releaseMajor" "releaseMinor" integers
        m={
          "repo":"_user", "lang":"ar", "type": int(self._is_tafseer(bkid)),
          "version":"0."+str(bkid), "releaseMajor":0, "releaseMinor":0,
          'originalKitab':None, 'originalVersion':None,
          'originalAuthor':None, 'originalYear':None
        }
        m['kitab']=makeId(r['bk'])
        m['author'],m['year']=self.authorByID(r['authno'], r)
        m['classification']=self.classificationByBookId(bkid)
        m['keywords']=u''
        matn_bkid=self._get_matn(bkid)
        #print "%d is sharh for %d" % (bkid, matn_bkid)
        if matn_bkid>0:
          matn_m=self.getBookMeta(matn_bkid)
          if matn_m:
            m['originalKitab']=matn_m['kitab']
            m['originalVersion']=matn_m['version']
            m['originalAuthor']=matn_m['author']
            m['originalYear']=matn_m['year']
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
  def __repr__(self):
    return (u"<start={0}, end={1}, txt={2}>".format(self.start, self.end, self.txt)).encode('utf-8')

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

def reformat(txt, shorts_t, shorts_dict):
  txt=txt.replace('\n','\n\n')
  if shorts_t & 1:
    for k in std_shorts:
      txt=txt.replace(k,std_shorts[k])
  for k in shorts_dict:
    txt=txt.replace(k,"\n====== %s ======\n\n" % shorts_dict[k])
  return txt

def set_get_xref(xref, h_tags, sh, bkid, pg_id, matn, matnid):
  h_tags['header']=xref
  sh.set_xref(bkid, pg_id, xref)
  if matn and matnid and sh.metaById.has_key(matn):
    m=sh.metaById[matn]
    xref=sh.get_xref(matn, matnid)
    if xref: h_tags['embed.original.section']=xref

ss_re=re.compile(" +")
re_ss_re=re.compile("( \*){2,}")

def ss(txt):
  """squeeze spaces"""
  return ss_re.sub(" ", txt)

def re_ss(txt):
  """squeeze spaces in re"""
  return re_ss_re.sub(" *", ss(txt))


def shamelaImport(cursor, sh, bkid, footnote_re=ur'\((\d+)\)', body_footnote_re=ur'\((\d+)\)', ft_prefix_len=1, ft_suffix_len=1):
  """
  import a ShamelaSqlite book as thawab kitab object, where
    * cursor - a cursor for an empty thawab kitab object
    * sh - ShamelaSqlite object
    * bkid - the id of the shamela book to be imported
  this function returns the cached meta dictionary
  """
  global footnotes_cnd, footnotes
  shamela_footer_re=re.compile(footnote_re, re.M | re.U)
  shamela_shift_footers_re=re.compile(body_footnote_re, re.M | re.U)
  ki=cursor.ki
  # NOTE: page id refers to the number used as id in shamela not thawab
  c=sh.c
  # step 0: prepare shorts
  shorts_t=c.execute("SELECT islamshort FROM main WHERE bkid=?", (bkid,)).fetchone()
  if shorts_t: shorts_t=shorts_t[0]
  else: shorts_t=0
  if shorts_t>1:
    shorts_dict=dict(c.execute("SELECT ramz,nass FROM shorts WHERE bk=?", (bkid,)).fetchall())
  else: shorts_dict={}
  # step 1: import meta
  meta=sh.getBookMeta(bkid)
  ki.setMCache(meta)
  # step 2: prepare topics hashed by page_id
  r=c.execute("SELECT id,tit,lvl FROM t%d ORDER BY id,sub" % bkid).fetchall()
  # NOTE: we only need page_id,title and depth, sub is only used to sort them
  toc_ls=filter(lambda i: i[2] and i[1], [list(i) for i in r])
  if not toc_ls: raise TypeError # no text in the book
  if toc_ls[0][0]!=1: toc_ls.insert(0, [1, sh.getBookMeta(bkid)['kitab'].replace('_',' '),toc_ls[0][2]])
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
      candidate=_foundShHeadingMatchItem(m.start(), m.start(), h, d, fuzzy) # NOTE: since this is not exact, make it ends at start. FIXME: it was m.end()
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
      # search for entire line matches (exact, then only letters and digits then only letters: 1,2,3)
      # search for leading matches (exact, then only letters and digits then only letters: 4,5,6)
      # search for matches anywhere (exact, then only letters and digits then only letters: 7,8,9)
      if _shamelaFindExactHeadings(page_txt, page_id, "\n%s\n", d, h, ix,j, 1): continue
      if not txt: txt=no_w_re.sub(' ', page_txt.translate(sh_normalize_tb))
      h_p=no_w_re.sub(' ', h.translate(sh_normalize_tb)).strip()
      if h_p: # if normalized h_p is not empty
        # NOTE: no need for map h_p on re.escape() because it does not contain special chars
        h_re_entire_line=re.compile(re_ss(ur"^\s*%s\s*$" % ur" *".join(list(h_p))), re.M)
        if _shamelaFindHeadings(txt, page_id, d, h, h_re_entire_line, ix, j, 2): continue

      if not txt_no_d: txt_no_d=txt.translate(sh_digits_to_spaces_tb)
      h_p_no_d=h_p.translate(sh_digits_to_spaces_tb).strip()
      if h_p_no_d:
        h_re_entire_line_no_d=re.compile(re_ss(ur"^\s*%s\s*$" % ur" *".join(list(h_p_no_d))), re.M)
        if _shamelaFindHeadings(txt_no_d, page_id, d, h, h_re_entire_line_no_d, ix, j, 3): continue

      # at the beginning of the line
      if _shamelaFindExactHeadings(page_txt, page_id, "\n%s", d, h, ix,j, 4): continue
      if h_p:
        h_re_line_start=re.compile(re_ss(ur"^\s*%s\s*" % ur" *".join(list(h_p))), re.M)
        if _shamelaFindHeadings(txt, page_id, d, h, h_re_line_start, ix, j, 5): continue
      if h_p_no_d:
        h_re_line_start_no_d=re.compile(re_ss(ur"^\s*%s\s*" % ur" *".join(list(h_p_no_d))), re.M)
        if _shamelaFindHeadings(txt_no_d, page_id, d, h, h_re_line_start_no_d, ix, j, 6): continue
      # any where in the line
      if _shamelaFindExactHeadings(page_txt, page_id, "%s", d, h, ix,j, 7): continue
      if h_p:
        h_re_any_ware=re.compile(re_ss(ur"\s*%s\s*" % ur" *".join(list(h_p))), re.M)
        if _shamelaFindHeadings(txt, page_id, d, h, h_re_any_ware, ix, j, 8): continue
      if h_p_no_d:
        h_re_any_ware_no_d=re.compile(re_ss(ur"\s*%s\s*" % ur" *".join(list(h_p_no_d))), re.M)
        if _shamelaFindHeadings(txt_no_d, page_id, d, h, h_re_any_ware, ix, j, 9): continue
      # if we reached here then head is not found
      # place it just after last one
      if found:
        last_end=found[-1].end
        #try: last_end+=page_txt[last_end:].index('\n')+1
        #except ValueError: last_end=len(page_txt); print "*"
        #print "last_end=",last_end
      else: last_end=0
      candidate=_foundShHeadingMatchItem(last_end, last_end, h, d, 0)
      bisect.insort(found, candidate) # add the candidate to the found list
    del toc_hash[page_id]
    return

  footnotes_cnd=[]
  footnotes=[]
  h_tags={}
  t_tags0={'textbody':None}
  t_tags=t_tags0.copy()
  last_hno=None
  hno_pop_needed=False

  def pop_footers(ft):
    s="\n\n".join(map(lambda (i,a): "  * (%d) %s" % (i+1,a[1]),enumerate(ft)))
    del ft[:]
    return s

  # step 3: walk through pages, accumulating contents  
  # NOTE: in some books id need not be unique
  # 
  blnk_base=sh.getBLink(bkid)
  blnk=""
  blnk_old=""
  r=c.execute('SELECT rowid FROM b%d ORDER BY rowid DESC LIMIT 1' % bkid).fetchone()
  r_max=float(r['rowid'])/100.0
  for r in c.execute('SELECT b%d.rowid,id,nass,part,page,hno,sora,aya,na,matn,matnid,blnk FROM b%d LEFT OUTER JOIN shrooh ON shrooh.sharh=%d AND id=shrooh.sharhid ORDER BY id' % (bkid,bkid,bkid,)):
    if sh.progress_dict.get('cancel', False): return None
    # FIXME: since we are using ORDER BY id, then using rowid for progress is not always correct
    sh.progress("importing book [%d]" % bkid, r['rowid']/r_max, *sh.progress_args, **sh.progress_kw)
    if r['nass']: pg_txt=r['nass'].translate(dos2unix_tb).strip()
    else: pg_txt=u""
    pg_id=r['id']
    hno=r['hno']
    blnk_old=blnk
    blnk=r['blnk']
    try:
      matn=r['matn'] and int(r['matn'])
      matnid=r['matnid'] and int(r['matnid'])
    except ValueError: matn,matnid=None,None
    except TypeError: matn,matnid=None,None

    sura,aya,na=0,0,0
    if r['sora'] and r['aya'] and r['sora']>0 and r['aya']>0:
      sura,aya,na=r['sora'],r['aya'],r['na']
      if not na or na<=0: na=1
      h_tags['quran.tafseer.ref']="%03d-%03d-%03d" % (sura,aya,na)

    # split pg_txt into pg_body and pg_footers_txt
    m=shamela_footers_re.search(pg_txt)
    if m:
      i=m.start()
      pg_body=pg_txt[:i].strip()
      pg_footers_txt=pg_txt[m.end()+1:].strip()
      # A=[(mark, offset_of_num, offset_of_text)]
      A=[(fm.group(1),fm.start(),fm.start()+len(fm.group(1))+ft_prefix_len+ft_suffix_len) for fm in shamela_footer_re.finditer(pg_footers_txt)] # fixme it need not be +2
      if A:
        pg_footers_continue=pg_footers_txt[:A[0][1]].strip()
        B=[]
        for i,(j,k,l) in enumerate(A[:-1]):
          # TODO: do we need to check if j is in right order
          B.append([j,pg_footers_txt[l:A[i+1][1]].strip()])
        j,k,l=A[-1]
        B.append([j,pg_footers_txt[l:].strip()])
        last_digit=0
        for i,j in B:
          if i.isdigit():
            if int(i)==last_digit+1:
              footnotes_cnd.append([i,j])
              last_digit=int(i)
            elif footnotes_cnd: footnotes_cnd[-1][1]+=" (%s) %s" % (i,j)
            else: pg_footers_continue+="(%s) %s" % (i,j)
          else: footnotes_cnd.append([i,j])
        if pg_footers_continue:
          # FIXME: should this be footnotes or footnotes_cnd
          if footnotes: footnotes[-1][1]+=" "+pg_footers_continue
          else:
            # NOTE: an excess footnote without previous footnotes to add it to
            print "  * warning: an excess text in footnotes in pg_id=",pg_id
            pg_body+="\n\n==========\n\n"+pg_footers_continue+"\n\n==========\n\n"
            # NOTE: t_tags is used since h_tags was already committed
            t_tags["request.fix.footnote"]="shamela import warning: excess text in footnotes"
    else: pg_body=pg_txt
    # debug stubs
    #if pg_id==38:
    #  print "pg_body=[%s]\n" % pg_body
    #  for j,k in footnotes_cnd:
    #    print "j=[%s] k=[%s]" % (j,k)
    #  # raise KeyError
    if toc_hash.has_key(pg_id):
      hno_pop_needed=False
    elif hno!=None and hno!=last_hno:
      # FIXME: make it into a new head
      last_hno=hno
      # commit anything not commited
      if footnotes:
        last+="\n\n__________\n"+pop_footers(footnotes)
      cursor.appendNode(parents[-1], reformat(last, shorts_t, shorts_dict), t_tags)
      t_tags=t_tags0.copy()
      last=""
      # create a new node
      set_get_xref(unicode(hno), h_tags, sh, bkid, pg_id, matn, matnid)
      h_tags[u'request.fix.head']=u'shamela import warning: automatically generated head'
      # FIXME: handle the case of a new hno on the beginning of a chapter
      if hno_pop_needed:
        parents.pop(); depths.pop() # FIXME: how many time to pop ?
      else: hno_pop_needed=True
      parent=cursor.appendNode(parents[-1], unicode(hno), h_tags); h_tags={}
      parents.append(parent)
      depths.append(depths[-1]+0.5) # FIXME: does this hack work?


    # TODO: set the value of header tag to be a unique reference
    # TODO: keep part,page,hno,sora,aya,na somewhere in the imported document
    # TODO: add special handling for hadeeth number and tafseer info
    found=[]
    # step 4: for each page content try to find all headings
    _shamelaHeadings(pg_body, pg_id)
    # now we got all headings in found
    # step 5: add the found headings and its content
    # splitting page text pg_body into [:f0.start] [f0.end:f1.start] [f1.end:f2.start]...[fn.end:]
    # step 5.1: add [:f0.start] to the last heading contents and push it
    if not found:
      # if no new heading in this page, add it to be committed later
      last+=shamela_shift_footers_re.sub(footer_shift_cb, pg_body)
      if footnotes_cnd:
        print " * fixing stall footnotes at pg_id=",pg_id
        last+=" ".join(map(lambda (j,k): "(%s) %s" % (j,k),footnotes_cnd))
        del footnotes_cnd[:]
      continue
    # here some new headings were found
    _fixHeadBounds(pg_body, found)
    # commit the body of previous heading first
    if started:
      if blnk_old and blnk_base:
        last+=u"\n\n[[%s]]\n\n" % (blnk_base+blnk_old)
        blnk_old=None
      last+=shamela_shift_footers_re.sub(footer_shift_cb, pg_body[:found[0].start])
      if footnotes_cnd:
        print " ** stall footnotes at pg_id=",pg_id
        #for j,k in footnotes_cnd:
        #  print "j=[%s] k=[%s]" % (j,k)
        #raise
      if footnotes:
        last+="\n\n__________\n"+pop_footers(footnotes)
      cursor.appendNode(parents[-1], reformat(last, shorts_t, shorts_dict), t_tags)
      t_tags=t_tags0.copy()
      last=""
    # step 5.2: same for all rest segments [f0.end:f1.start],[f1.end:f2.start]...[f(n-1).end:fn.start]
    for i,f in enumerate(found[:-1]):
      while(depths[-1]>=f.depth): depths.pop(); parents.pop()
      started=True
      # FIXME: pg_id won't be unique, add a counter like "_p5", "_p5.2", ..etc
      set_get_xref(u"_p"+unicode(pg_id), h_tags, sh, bkid, pg_id, matn, matnid)
      if f.fuzzy==0: h_tags[u'request.fix.head']=u'shamela import error: missing head'
      parent=cursor.appendNode(parents[-1], f.txt+f.suffix, h_tags); h_tags={}
      parents.append(parent)
      depths.append(f.depth)
      last=shamela_shift_footers_re.sub(footer_shift_cb, pg_body[f.end:found[i+1].start])
      if footnotes: last+="\n\n__________\n"+pop_footers(footnotes)
      parent=cursor.appendNode(parent, reformat(last, shorts_t, shorts_dict), t_tags)
      t_tags=t_tags0.copy()
    # step 5.3: save [fn.end:] as last heading
    f=found[-1]
    while(depths[-1]>=f.depth): depths.pop(); parents.pop()
    # FIXME: pg_id won't be unique, add a counter like "_p5", "_p5.2", ..etc
    set_get_xref(u"_p"+unicode(pg_id), h_tags, sh, bkid, pg_id, matn, matnid)
    txt_start=f.end
    if f.fuzzy==0: h_tags[u'request.fix.head']=u'shamela import error: missing header'
    parent=cursor.appendNode(parents[-1], f.txt+f.suffix,h_tags); h_tags={}
    started=True
    parents.append(parent)
    depths.append(f.depth)
    #last=pg_body[f.end:]+'\n'
    last=shamela_shift_footers_re.sub(footer_shift_cb, pg_body[f.end:]+'\n')
    if footnotes_cnd:
      last+="\n==========[\n"+pop_footers(footnotes_cnd)+"\n]==========\n"
    

  if not started: raise TypeError
  if blnk and blnk_base:
    last+=u"\n\n[[%s]]\n\n" % (blnk_base+blnk)
    blnk=None
  if last:
    if footnotes:
      last+="\n\n__________\n"+pop_footers(footnotes)
    cursor.appendNode(parents[-1], reformat(last, shorts_t, shorts_dict), t_tags)
    t_tags=t_tags0.copy()
  # l should be empty because we have managed missing headers
  #l=filter(lambda i: i,toc_hash.values())
  #for j in l: print j
  #print "*** headings left: ",len(l)
  sh.metaById[bkid]=meta
  sh.progress("importing book [%d]" % bkid, 100.0, *sh.progress_args, **sh.progress_kw)
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

