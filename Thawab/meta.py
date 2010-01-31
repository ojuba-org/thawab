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
import time
import hashlib
from itertools import imap,groupby
from dataModel import *
from okasha.utils import strverscmp
import re

def prettyId(i, empty_for_special=True):
  """convert the id into a more human form"""
  if empty_for_special and i.startswith('_'): return ''
  return i.replace('_',' ')

def makeId(i):
  """convert the id into a canonical form"""
  return i.strip().replace(' ','_')

def metaVr(m):
  return m[u"version"]+u"-"+m[u"releaseMajor"]

def metaVrr(m):
  return u"-".join((m[u"version"],m[u"releaseMajor"],m[u"releaseMinor"]))


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
    if not os.path.exists(mcache_db): create_new=True
    else: create_new=False
    self.__cn=sqlite3.connect(mcache_db, isolation_level=None)
    self.__cn.row_factory=sqlite3.Row
    self.__c=self.__cn.cursor()
    if create_new:
      self.__c.executescript(SQL_MCACHE_DATA_MODEL)
    self.__reload()
    if self.__create_cache(uri_list, smart)>0: self.__reload()

  def __reload(self):
    self.__meta=map(lambda i: dict(i), self.__c.execute(SQL_MCACHE_GET_BY_KITAB))
    self.__meta_by_uri=(dict(map(lambda a: (a[1]['uri'],a[0]),enumerate(self.__meta))))
    self.__meta_uri_list=self.__meta_by_uri.keys()
    self.__meta_by_kitab={}
    for k,G in groupby(enumerate(self.__meta),lambda a: a[1]['kitab']):
      g=list(G)
      self.__meta_by_kitab[k]=map(lambda i: i[0],g)

  def __load_from_uri(self, uri):
    """extract meta object from kitab's uri and return it"""
    cn=sqlite3.connect(uri)
    cn.row_factory=sqlite3.Row
    c=cn.cursor()
    r=c.execute(SQL_MCACHE_GET).fetchone()
    if not r: return None
    return dict(r)

  def __cache(self, uri, meta=None):
    if not meta: meta=self.__load_from_uri(uri)
    if not meta: return 0
    #if drop_old_needed: 
    meta['uri']=uri
    meta['mtime']=os.path.getmtime(uri)
    meta['flags']=0
    self.__c.execute(SQL_MCACHE_ADD,meta)
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
    r=0
    self.__c.execute('BEGIN TRANSACTION')
    # remove meta for kitab that no longer exists
    deleted=filter(lambda i: i not in uri_list, self.__meta_uri_list)
    for uri in deleted:
      self.__c.execute(SQL_MCACHE_DROP, (uri,))
      r+=1
    # update meta for the rest (in a smart way)
    for uri in uri_list:
      if smart==0:
        # force recreation of cache, drop all, then create all
        r+=self.__cache(uri, uri in self.__meta_uri_list)
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
          if abs(os.path.getmtime(uri)-self.getByUri(uri)['mtime'])<1e-5: continue
        elif smart==1: # rely on a hash saved inside the database
          old_meta=self.getByUri(uri)
          meta=self.__load_from_uri(uri)
          if not meta or old_meta['hash']==meta['hash']: continue
      if cache_needed:
        r+=self.__cache(uri, meta)
    self.__c.execute('END TRANSACTION')
    self.__cn.commit()
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
    a=self.__meta_by_kitab.get(kitab,None)
    ma=filter(lambda m: m[u'version']==v and m[u'releaseMajor']==r,[self.__meta[i] for i in a])
    if not ma: return None
    return self._latest(ma)

