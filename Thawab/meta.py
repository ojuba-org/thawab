# -*- coding: UTF-8 -*-
"""
The meta handling classes of thawab
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
import os
import os.path
import sqlite3
import threading
import time
import hashlib
from itertools import imap,groupby
from dataModel import *
from okasha.utils import fromFs, toFs, strverscmp
import re

def prettyId(i, empty_for_special=True):
  """convert the id into a more human form"""
  if empty_for_special and i.startswith('_'): return ''
  return i.replace('_',' ')

def makeId(i):
  """convert the id into a canonical form"""
  return i.strip().replace(' ','_').replace('/','_')

def metaVr(m):
  return m[u"version"]+u"-"+unicode(m[u"releaseMajor"])

def metaVrr(m):
  return u"-".join((m[u"version"],unicode(m[u"releaseMajor"]),unicode(m[u"releaseMinor"])))


def metaDict2Hash(meta, suffix=None):
  k=filter(lambda i: i!='cache_hash',meta.keys())
  k.sort()
  l=[]
  for i in k:
    l.append(u"%s:%s" % (i,meta[i]))
  l.append(u"timestamp:%d" % int(time.time()))
  if suffix: l.append(suffix)
  return hashlib.sha256((u"-".join(l)).encode('utf-8')).digest().encode('base64').strip()[:-1]

class MCache(object):
  """a class holding metadata cache"""
  def __init__(self, mcache_db, uri_list, smart=-1):
    self.db_fn = mcache_db
    if not os.path.exists(mcache_db): create_new=True
    else: create_new=False
    self._cn={}
    cn=self._getConnection()
    if create_new:
      cn.executescript(SQL_MCACHE_DATA_MODEL)
      cn.commit()
    self.__reload()
    if self.__create_cache(uri_list, smart)>0: self.__reload()

  def _getConnection(self):
    n = threading.current_thread().name
    if self._cn.has_key(n):
      r = self._cn[n]
    else:
      r = sqlite3.connect(self.db_fn)
      r.row_factory=sqlite3.Row
      self._cn[n] = r
    return r


  def __reload(self):
    self.__meta=map(lambda i: dict(i), self._getConnection().execute(SQL_MCACHE_GET_BY_KITAB))
    self.__meta_by_uri=(dict(map(lambda a: (a[1]['uri'],a[0]),enumerate(self.__meta))))
    self.__meta_uri_list=self.__meta_by_uri.keys()
    self.__meta_by_kitab={}
    for k,G in groupby(enumerate(self.__meta),lambda a: a[1]['kitab']):
      g=list(G)
      self.__meta_by_kitab[k]=map(lambda i: i[0],g)

  def load_from_uri(self, uri):
    """extract meta object from kitab's uri and return it"""
    cn=sqlite3.connect(uri)
    cn.row_factory=sqlite3.Row
    c=cn.cursor()
    r=c.execute(SQL_MCACHE_GET).fetchone()
    if not r: return None
    return dict(r)

  def __cache(self, c, uri, meta=None):
    if not meta: meta=self.load_from_uri(uri)
    if not meta: return 0
    #if drop_old_needed: 
    meta['uri']=uri
    meta['mtime']=os.path.getmtime(toFs(uri))
    meta['flags']=0
    c.execute(SQL_MCACHE_ADD,meta)
    return 1

  def __create_cache(self, uri_list, smart=-1):
    """
    create cache and return the number of newly created meta caches
    
    smart is how fast you want to do that:
      * 0 force regeneration of entire meta cache
      * 1 regenerate cache when hash differs (it would need to open every kitab)
      * 2 regenerate when mtime differs
      * -1 do not update cache for exiting meta (even if the file is changed)
    """
    cn = self._getConnection()
    c=cn.cursor()
    r=0
    uri_set=set(uri_list)
    #c.execute('BEGIN TRANSACTION')
    # remove meta for kitab that no longer exists
    deleted=filter(lambda i: i not in uri_set, self.__meta_uri_list)
    for uri in deleted:
      c.execute(SQL_MCACHE_DROP, (uri,))
      r+=1
    # update meta for the rest (in a smart way)
    for uri in uri_list:
      if not os.access(toFs(uri), os.R_OK): continue
      if smart==0:
        # force recreation of cache, drop all, then create all
        r+=self.__cache(c, uri, uri in self.__meta_uri_list)
        continue
      meta=None
      drop_old_needed=False
      cache_needed=False
      if uri not in self.__meta_uri_list:
        cache_needed=True
      else:
        drop_old_needed=True
        cache_needed=True
        if smart==-1: continue # don't replace existing cache
        elif smart==2: # rely of mtime
          if abs(os.path.getmtime(toFs(uri))-self.getByUri(uri)['mtime'])<1e-5: continue
        elif smart==1: # rely on a hash saved inside the database
          old_meta=self.getByUri(uri)
          meta=self.load_from_uri(uri)
          if not meta or old_meta['hash']==meta['hash']: continue
      if cache_needed:
        r+=self.__cache(c, uri, meta)
    #c.execute('END TRANSACTION')
    cn.commit()
    return r

  def getKitabList(self):
    return self.__meta_by_kitab.keys()

  def getUriList(self):
    return self.__meta_by_uri.keys()

  def getByUri(self, uri):
    """return meta object for uri"""
    i=self.__meta_by_uri.get(uri,None)
    if i==None: return None
    return self.__meta[i]

  def getByKitab(self, kitab):
    """return a list of meta objects for a kitab"""
    a=self.__meta_by_kitab.get(kitab,None)
    if not a: return None
    return map(lambda i: self.__meta[i], a)

  def _latest(self, a):
    lm=a[0]
    l=metaVrr(lm)
    for m in a[1:]:
      v=metaVrr(m)
      if strverscmp(v, l)>0: lm=m; l=v
    return lm

  def getLatestKitab(self, kitab):
    """return a meta object for latest kitab (based on version)"""
    a=self.__meta_by_kitab.get(kitab,None)
    if not a: return None
    return self._latest([self.__meta[i] for i in a])

  def getLatestKitabV(self, kitab, v):
    """
    given kitab name and version
    return a meta object for latest kitab (based on version)
    """
    a=self.__meta_by_kitab.get(kitab,None)
    ma=filter(lambda m: m[u'version']==v,[self.__meta[i] for i in a])
    if not ma: return None
    return self._latest(ma)

  def getLatestKitabVr(self, kitab, v, r):
    """
    given kitab name and version and major release
    return a meta object for latest kitab (based on version)
    """
    if type(r)!=int: r=int(r)
    a=self.__meta_by_kitab.get(kitab,None)
    ma=filter(lambda m: m[u'version']==v and m[u'releaseMajor']==r,[self.__meta[i] for i in a])
    if not ma: return None
    return self._latest(ma)

  def setIndexedFlags(self, uri, flags=2):
    cn = self._getConnection()
    cn.execute(SQL_MCACHE_SET_INDEXED, (flags, uri,))
    cn.commit()

  def setAllIndexedFlags(self, flags=0):
    cn = self._getConnection()
    cn.execute(SQL_MCACHE_SET_ALL_INDEXED, (flags,))
    cn.commit()

  def getUnindexedList(self):
    """
    return a list of meta dicts for Kutub that are likely to be unindexed
    """
    
    return map(lambda i: dict(i), self._getConnection().execute(SQL_MCACHE_GET_UNINDEXED))

  def getDirtyIndexList(self):
    """
    return a list of meta dicts for Kutub that are likely to have broken index
    """
    return map(lambda i: dict(i), self._getConnection().execute(SQL_MCACHE_GET_DIRTY_INDEX))

  def getIndexedList(self):
    """
    return a list of meta dicts for Kutub that are already in index.
    """
    return map(lambda i: dict(i), self._getConnection().execute(SQL_MCACHE_GET_INDEXED))


