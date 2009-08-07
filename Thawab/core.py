# -*- coding: utf-8 -*-
"""
The core classes of thawab
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
#import threading
from glob import glob
from itertools import imap,groupby
from tempfile import mkstemp
from StringIO import StringIO
from xml.sax.saxutils import escape, unescape, quoteattr # for xml rendering
from dataModel import *
from tags import *
from meta import MCache

import re
th_ext='.ki'
th_ext_glob='*.ki'

class ThawabMan (object):
  def __init__(self,user_prefix,system_prefix=""):
    """Create a new Thawab instance given a user writable directory and an optional system-wide read-only directory

  user_prefix can be:
    user_prefix=os.path.expanduser('~/.thawab')
    user_prefix=os.path.join([os.path.dirname(sys.argv[0]),'..','data'])
  
  and system_prefix is a system-wide read-only directory like "/usr/share/thawab/"

the first thing you should do is to call loadMCache()
"""
    try:
      if not os.path.isdir(user_prefix): os.makedirs(user_prefix)
    except:
      raise OSError
    self.prefixes=[os.path.abspath(user_prefix)]
    self.__meta=None
    if system_prefix and os.path.isdir(system_prefix):
      self.prefixes.append(os.path.abspath(system_prefix))
    self.assertManagedTree()
    self.__ix_writer = None
    self.__init_indexer()

  def assertManagedTree(self):
     """create the hierarchy inside the user-managed prefix    
     # db	contains Kitab files [.thawab]
     # index	contains search index
     # conf	application configuration
     # cache	contains the metadata cache for all containers"""
     P=self.prefixes[0]
     for i in ['db','index','conf','cache','tmp']:
       p=os.path.join(P,i)
       if not os.path.isdir(p): os.makedirs(p)
  def mktemp(self):
    h,fn=mkstemp(th_ext, 'THAWAB_',os.path.join(self.prefixes[0],'tmp'))
    return Kitab(fn,True)
  def getKitab(self,kitabName):
    if not self.managedLoaded: self.loadMCache()
    return Kitab(self.managed[kitabName]['uri'])
  def getManagedUriList(self):
    """list of all managed uri (absolute filenames for a Kitab)
     this is low level as the user should work with kitabName, title, and rest of meta data"""
    if self.__meta:
      return self.__meta.get_uri_list()
    r=[]
    for i in self.prefixes:
      p=glob(os.path.join(i,'db',th_ext_glob))
      r.extend(p)
    return r
  def getMeta(self):
    if not self.__meta: self.loadMeta()
    return self.__meta
  def loadMeta(self):
    p=os.path.join(self.prefixes[0],'cache','meta.db')
    self.__meta=MCache(p, self.getManagedUriList())

  ##############################
  # search index related
  ##############################
  def __init_indexer(self):
    self.__ix_writer = None
    try:
      import whoosh
      import whoosh.qparser
      import whoosh.query
      from indexing import StemFilter, TAGSLIST
    except: raise # while developing we want to know when we got a problem
    #except ImportError: self.indexer=None; return
    ix_dir=os.path.join(self.prefixes[0],'index')
    store=whoosh.store.FileStorage(ix_dir)
    analyzer=whoosh.analysis.StemmingAnalyzer()
    analyzer.tokenizer=whoosh.analysis.SpaceSeparatedTokenizer()
    analyzer.stemfilter=StemFilter()
    # try to load a pre-existing index
    try:
      self.indexer=whoosh.index.Index(store)
    except whoosh.index.EmptyIndexError:
      # create a new one
      schema=whoosh.fields.Schema( \
        # TODO: a single uniq field documentId=kitabName:nodeIdNum or two fields
        kitabName=whoosh.fields.ID(stored=True,unique=False), 
        nodeIdNum=whoosh.fields.ID(stored=True,unique=False), 
        title=whoosh.fields.TEXT(stored=True,field_boost=1.5), content=whoosh.fields.TEXT(analyzer=analyzer),
        tags=TAGSLIST(lowercase=True)
      )
      self.indexer=whoosh.index.Index(store,schema, True)
    self.__ix_qparser = whoosh.qparser.MultifieldParser(("title","content",), schema=self.indexer.schema)
    #self.__ix_pre=whoosh.query.Prefix
    self.__ix_searcher= self.indexer.searcher()

  def __del__(self):
    if self.__ix_writer: self.__ix_writer.commit()

  def ix_refresh(self):
    self.indexer=self.indexer.refresh()
    self.__ix_searcher= self.indexer.searcher()
    self.__ix_writer = None

  # FIXME: all the index routines uses uri not kitsabName as the variable suggests, make them consistent
  # FIXME: a method needed that call commit and optimize and refresh
  def reIndexAll(self):
    t=[]
    if not self.__ix_writer: self.__ix_writer=self.indexer.writer()
    for i in self.getManagedUriList(): self.reIndex(i)
    #for i in self.getManagedUriList():
    #  t.append(threading.Thread(target=self.reIndex,args=(i,)))
    #  t[-1].start()
    #for i in t: i.join()
    self.__ix_writer.commit()
    self.indexer.optimize()
    self.ix_refresh()

  class __IIX(object):
    "internal indexing object"
    def __init__(self):
      # independent arrays
      self.contents=[] # array of contents to be indexed
      self.tags=[] # array of ix tags
      # main_f* parallel arrays
      self.main_f_node_idnums=[] # array of node.idNum of consuming ix fields (ie. header)
      self.main_f_content_index=[] # array of the starting index in self.contents for each main ix field (ie. header)
      self.main_f_tags_index=[] # array of the starting index in self.contents for each main ix field (ie. header)
      # sub_f* parallel arrays
      self.sub_f_node_idnums=[] # array of node.idNum for each sub ix field
      self.sub_f_content_index=[] # array of the starting index in self.contents for each sub ix field
      self.sub_f_tags_index=[] # array of the starting index in self.tags for each sub ix field
      # TODO: benchmark which is faster parallel arrays or small tubles sub_field=(idNum,content_i,tag_i)

  def __ix_nodeStart(self, node, kitabName, iix):
    # NOTE: benchmarks says append then join is faster than s+="foo"
    tags=node.getTags()
    tag_flags=node.getTagFlags()
    # create new consuming main indexing fields [ie. headers]
    # TODO: let loadToc use TAG_FLAGS_HEADER instead of hard-coding 'header'
    #if node.getTagsByFlagsMask(TAG_FLAGS_HEADER):
    # NOTE: for consistency, header is the only currentely allowed tag having TAG_FLAGS_HEADER
    if tag_flags & TAG_FLAGS_HEADER:
      iix.main_f_node_idnums.append(node.idNum)
      iix.main_f_content_index.append(len(iix.contents))
      iix.main_f_tags_index.append(len(iix.tags))
    # create new sub non-consuming indexing fields
    if tag_flags & TAG_FLAGS_IX_FIELD:
      iix.sub_f_node_idnums.append(node.idNum)
      iix.sub_f_content_index.append(len(iix.contents))
      iix.sub_f_tags_index.append(len(iix.tags))
    # TODO: check for nodes that are not supposed to be indexed TAG_FLAGS_IX_SKIP
    # append ix contents
    iix.contents.append(node.getContent()) # TODO: append extra padding space if TAG_FLAGS_PAD_CONTENT
    # append ix tags
    iix.tags.extend(map(lambda t: tags[t]==None and t or u'.'.join((t,tags[t])), node.getTagsByFlagsMask(TAG_FLAGS_IX_TAG)))
  
  def __ix_nodeEnd(self, node, kitabName, iix):
    # index extra sub fields if any
    if iix.sub_f_node_idnums and iix.sub_f_node_idnums[-1]==node.idNum:
      n=iix.sub_f_node_idnums.pop()
      i=iix.sub_f_content_index.pop()
      j=iix.sub_f_tags_index.pop()
      c=u"".join(iix.contents[i:])
      T=u" ".join(iix.tags[j:])
      del iix.tags[j:]
      k=iix.main_f_content_index[-1] # the nearest header title index
      N=iix.main_f_node_idnums[-1] # the nearest header node.idNum
      # NOTE: the above two lines means that a sub ix fields should be children of some main field (header)
      t=iix.contents[k]
      self.__ix_writer.add_document(kitabName=unicode(kitabName), nodeIdNum=unicode(N), title=t, content=c, tags=T)
    # index consuming main indexing fields if any
    if iix.main_f_node_idnums and iix.main_f_node_idnums[-1]==node.idNum: 
      n=iix.main_f_node_idnums.pop()
      i=iix.main_f_content_index.pop()
      j=iix.main_f_tags_index.pop()
      t=iix.contents[i]
      c=u"".join(iix.contents[i:])
      del iix.contents[i:]
      T=u" ".join(iix.tags[j:])
      del iix.tags[j:]
      self.__ix_writer.add_document(kitabName=unicode(kitabName), nodeIdNum=unicode(n), title=t, content=c, tags=T)


  def createIndex(self,uri):
    """create search index for a given Kitab uri"""
    print "creating index for uri:", uri
    if not self.__ix_writer: self.__ix_writer=self.indexer.writer()
    ki=Kitab(uri)
    iix=self.__IIX()
    ki.root.traverser(3, self.__ix_nodeStart, self.__ix_nodeEnd, uri, iix)
    
  def dropIndex(self, uri):
    """drop search index for a given Kitab by its uri"""
    # NOTE: because the searcher could be limited do a loop that keeps deleting till the query is empty
    print "dropping index for uri:", uri,
    while(self.indexer.delete_by_term('kitabName', uri)):
      print "*",
      pass # query just selects the kitabName
    print
    # NOTE: in case of having a documentId field prefixed with kitabName:
    #q=self.__ix_pre('documentId',kitabName+':')
    #self.indexer.delete_by_query(q,self.__ix_searcher) # TODO: loop because the searcher could be limited
    
  def reIndex(self,uri):
    # can't use updateDocument because each Kitab contains many documents
    self.dropIndex(uri); self.createIndex(uri)
  def queryIndex(self, queryString):
    """return an interatable of fields dict"""
    return self.__ix_searcher.search(self.__ix_qparser.parse(queryString))

class Kitab(object):
  """this class represents a book or an article ...etc."""
  def __init__(self,uri, is_tmp=False):
    """open the Kitab pointed by uri (or try to create it)"""
    # TODO: do we need a mode = r|w ?
    self.uri=uri
    self.is_tmp=is_tmp
    # the logic to open the uri goes here
    # check if fn exists, if not then set the flag sql_create_schema
    if is_tmp or not os.path.exists(uri): sql_create_schema=True
    else: sql_create_schema=False
    # 
    self.cn=sqlite3.connect(uri, isolation_level=None)
    self.cn.create_function("th_enumerate", 0, self.rowsEnumerator) # FIXME: do we really need this
    self.__c=self.cn.cursor() # TODO: have a policy when should the default sql cursor be used ? eg. only for reading
    # private
    self.__toc = [] # flat list of children Nodes having HEADER tag
    self.__tags = {} # a hash by of tags data by tag name
    self.__tags_loaded=False
    self.__counter = 0 # used to renumber rows
    self.inc_size=1<<10
    # TODO: make a decision, should the root node be saved in SQL, if so a lower bound checks to Kitab.getSliceBoundary() and an exception into Kitab.getNodeByIdNum()
    self.root=Node(kitab=self, idNum=0,parent=-1,depth=0,content='',tags={})
    if sql_create_schema:
      self.__c.executescript(SQL_DATA_MODEL)
      # create standard tags
      for t in STD_TAGS_ARGS:
        self.__c.execute(SQL_ADD_TAG,t)
    self.loadToc()
  def setMCache(self, meta):
    # TODO: add more checks
    a=meta.get('author',None)
    oa=meta.get('originalAuthor',None)
    if not a and oa: meta['author']=oa
    if not oa and a: meta['originalAuthor']=a
    y=meta.get('year',None)
    oy=meta.get('originalYear',None)
    if not y and oy: meta['year']=oy
    if not oy and y: meta['originalYear']=y
    self.__c.execute(SQL_MCACHE_SET,meta)
  ###################################
  # retrieving data from the Kitab
  ###################################
  def getTags(self):
    if not self.__tags_loaded: self.reloadTags()
    return self.__tags
  def reloadTags(self):
    self.__tags = dict(map(lambda r: (r[0],r[1:]),self.__c.execute(SQL_GET_ALL_TAGS).fetchall()))
    self.__tags_loaded=True

  def getNodeByIdNum(self, idNum, load_content=False):
    if idNum==0: return self.root
    r=self.__c.execute(SQL_GET_NODE_BY_IDNUM[load_content],(idNum,)).fetchone()
    if not r: raise IndexError, "idNum not found"
    r=list(r)
    if len(r)<=3: return Node(kitab=self, idNum=r[0],parent=r[1],depth=r[2])
    return Node(kitab=self, idNum=r[0],parent=r[1],depth=r[2],content=r[3])
  ##############################
  # manipulating Kitab's content
  ##############################
  # feeding content
  def __lock(self):
    # TODO: make it "BEGIN TRANS"
    pass
  def __unlock(self):
    pass
  def seek(self,parentNodeIdNum=-1,nodesNum=-1):
    """should be called before concatenating nodes, all descendents will be dropped
where:
  parentNodeIdNum	- the parent below which the concatenation will begin, -1 at the tail
  nodesNum		- number of nodes to be concatenated, -1 for unknown open number

nodesConcatenationStart()
concatenateNode(parentNodeIdNum, content, tags)
concatenateNode(parentNodeIdNum, content, tags)
...
nodesConcatenationEnd()
"""
    self.__lock()
    self.__is_tailing=False
    self.__is_tmp=False
    self.__tmp_str=''
    self.__parents=[]
    self.__c.execute('BEGIN TRANSACTION')
    # self.__last_go # last globalOrder
    if parentNodeIdNum!=-1:
      self.dropDescendants(parentNodeIdNum)
      if nodesNum==-1: self.__is_tmp=True; self.__tmp_str='tmp';
      else:
        # FIXME: make sure 
        raise IndexError, "not implented"
    else:
      self.__parents=[self.root]
      r=self.__c.execute(SQL_GET_LAST_GLOBAL_ORDER).fetchone()
      if r: self.__last_go=r[0]
      else: self.__last_go=0
      self.__is_tailing=True
  def flush(self):
    """Called after the last concatenateNode"""
    if self.__is_tmp:
      # TODO: implement using "insert into ... select tmp_nodes ...;"
      raise IndexError, "not implented"
    self.__c.execute('END TRANSACTION')
    #self.__c.execute('COMMIT')
    self.cn.commit()
    self.__unlock()
  def appendToCurrent(self, parentNode, content, tags):
    parentNodeIdNum=parentNode.idNum
    while(self.__parents[-1].idNum!=parentNodeIdNum): self.__parents.pop()
    new_go=self.__last_go+self.inc_size
    newid=self.__c.execute(SQL_APPEND_NODE[self.__is_tmp],(content, self.__parents[-1].idNum, new_go, self.__parents[-1].depth+1)).lastrowid
    self.__last_go=new_go
    node=Node(kitab=self, idNum=newid,parent=self.__parents[-1].idNum,depth=self.__parents[-1].depth+1)
    node.applyTags(tags)
    self.__parents.append(node)
    return node
  def getSliceBoundary(self, nodeIdNum):
    """return a tuble of o1,o2 where:
      o1: is the globalOrder of the given Node
      o2: is the globalOrder of the next sibling of the given node, -1 if unbounded
all the descendents of the given nodes have globalOrder belongs to the interval (o1,o2)
    """
    # this is a private method used by dropDescendants
    if nodeIdNum==0: return 0,-1
    r=self.__c.execute(SQL_GET_GLOBAL_ORDER,(nodeIdNum,)).fetchone()
    if not r: raise IndexError
    o1=r[0]
    parent=r[1]
    r=self.__c.execute(SQL_GET_SIBLING_GLOBAL_ORDER,(parent,o1)).fetchone()
    if not r: o2=-1
    else: o2=r[0]
    return o1,o2

  def dropDescendants(self,parentNodeIdNum, withParent=False):
    """remove all child nodes going deep at any depth, and optionally with their parent"""
    o1,o2=self.getSliceBoundary(parentNodeIdNum)
    if o2==-1:
      self.__c.execute(SQL_DROP_TAIL_NODES[withParent],(o1,))
    else:
      self.__c.execute(SQL_DROP_DESC_NODES[withParent],(o1,o2))
  # FIXME: do we really need this
  def rowsEnumerator(self):
    """private method used internally"""
    self.__counter+=self.inc_size
    return self.__counter
  def loadToc(self):
    self.__toc=list(self.root.descendantsWithTagNameIter('header'))
    self.__toc_loaded=True
    # for i in self.__toc: print i.depth,i.getContent()

class Node (object):
  """A node class returned by some Kitab methods, avoid creating your own

it has the following properities:
  kitab			the Kitab instance to which this node belonds, none if floating
  parent		the parent node idNum, -1 if root
  idNum			the node idNum, -1 if floating or not yet saved
  depth			the depth of node, -1 for floating, 0 for root
  tags			the applied tags, {tagname:param,...}, None if not loaded
and the following methods:
  getContent()		return node's content, loading it from back-end if needed
  reloadContent()	force reloading content
  unloadContent()	unload content to save memory
"""
  def __init__(self, **args):
    self.kitab=args.get('kitab')
    self.parent=args.get('parent',-1)
    self.idNum=args.get('idNum',-1)
    self.depth=args.get('depth',-1)
    self.__grouped_rows_to_node=(self.__grouped_rows_to_node0, self.__grouped_rows_to_node1, self.__grouped_rows_to_node2, self.__grouped_rows_to_node3)
    self.__row_to_node=(self.__row_to_node0, self.__row_to_node1)
    # TODO: should globalOrder be a properity ?
    try:
      self.__content=args['content']
      self.__content_loaded=True
    except KeyError: self.__content_loaded=False
    # TODO: should tags be called tagDict
    try:
      self.__tags=args['tags']
      self.__tags_loaded=True
    except KeyError: self.__tags_loaded=False
    try:
      self.__tag_flags=args['tag_flags']
      self.__tag_flags_loaded=True
    except KeyError: self.__tag_flags_loaded=False
    
  # tags related methods
  def getTags(self):
    """return tag dictionary applied to the node, loading it from back-end if needed"""
    if not self.__tags_loaded: self.reloadTags()
    return self.__tags
  def getTagFlags(self):
    """return the "or" summation of flags of all tags applied to this node"""
    if not self.__tag_flags_loaded: self.reloadTags()
    return self.__tag_flags

  def getTagsByFlagsMask(self, mask):
    """return tag names having flags masked with mask, used like this node.getTagsByFlagsMask(TAG_FLAGS_IX_TAG)"""
    # return filter(lambda t: STD_TAGS_HASH[t][2]&mask, self.getTags())
    return filter(lambda t: self.kitab.getTags()[t][0]&mask, self.getTags())
  def reloadTags(self):
    """force reloading of Tags"""
    self.__tags=dict(self.kitab.cn.execute(SQL_GET_NODE_TAGS,(self.idNum,)).fetchall())
    self.__tags_loaded=True
    T=map(lambda t: self.kitab.getTags()[t][0], self.__tags.keys())
    self.__tag_flags=reduce(lambda a,b: a|b,T, 0)
    self.__tag_flags_loaded=True
    
  def unloadTags(self):
    """unload content to save memory"""
    self.__tags_loaded=False
    self.__tags=None
    self.__tag_flags=0
    self.__tag_flags_loaded=False
  # content related methods
  def getContent(self):
    """return node's content, loading it from back-end if needed"""
    if not self.__content_loaded: self.reloadContent()
    return self.__content
  def reloadContent(self):
    """force reloading content"""
    r=self.kitab.cn.execute(SQL_GET_NODE_CONTENT,(self.idNum,)).fetchone()
    if not r:
      self.__content=None
      self.__content_loaded=False
      raise IndexError, 'node not found, could be a floating node'
    self.__content=r[0]
    self.__content_loaded=True
  def unloadContent(self):
    """unload content to save memory"""
    self.__content_loaded=False
    self.__content=None
  # tags editing
  def tagWith(self,tag,param=None):
    """apply a single tag to this node,
if node is already taged with it, just update the param
the tag should already be in the kitab."""
    
    r=self.kitab.cn.execute(SQL_TAG,(self.idNum,param,tag)).rowcount
    if not r: raise IndexError, "tag not found"

  def applyTags(self,tags):
    """apply a set of taga to this node,
if node is already taged with them, just update the param
each tag should already be in the kitab."""
    for k in tags:
      self.tagWith(k,tags[k])
  def clearTags(self):
    """clear all tags applyed to this node"""
    self.kitab.cn.execute(SQL_CLEAR_TAGS_ON_NODE,(self.idNum,))

  # internal node generators
  def __row_to_node0(self,r):
    return Node(kitab=self.kitab, idNum=r[0],parent=r[1],depth=r[2])
  def __row_to_node1(self,r):
    return Node(kitab=self.kitab, idNum=r[0],parent=r[1],depth=r[2],content=r[3])
  def __grouped_rows_to_node0(self,l):
    r=list(l[1])
    return Node(kitab=self.kitab, idNum=r[0][0],parent=r[0][1],depth=r[0][2])
  def __grouped_rows_to_node1(self,l):
    r=list(l[1])
    return Node(kitab=self.kitab, idNum=r[0][0],parent=r[0][1],depth=r[0][2],content=r[0][3])
  def __grouped_rows_to_node2(self,l):
    r=list(l[1])
    return Node(kitab=self.kitab, idNum=r[0][0],parent=r[0][1],depth=r[0][2], \
      tags=dict(map(lambda i: (i[3],i[4]),r)), tag_flags=reduce(lambda a,b: a[5]|b[5],r,(0,0,0,0,0,0)) )
  def __grouped_rows_to_node3(self,l):
    r=list(l[1])
    return Node(kitab=self.kitab, idNum=r[0][0],parent=r[0][1],depth=r[0][2], content=r[0][3], \
       tags=dict(map(lambda i: (i[4],i[5]),r)), tag_flags=reduce(lambda a,b: a[6]|b[6],r,(0,0,0,0,0,0,0)) )

  # methods that give nodes
  def childrenIter(self, preload=WITH_CONTENT_AND_TAGS):
    """an iter that retrieves all direct children of this node, just one level deeper, content and tags will be pre-loaded by default.
    
where preload can be:
  0  WITH_NONE
  1  WITH_CONTENT
  2  WITH_TAGS
  3  WITH_CONTENT_AND_TAGS
"""
    it=self.kitab.cn.execute(SQL_GET_CHILD_NODES[preload],(self.idNum,))
    # return imap(self.__grouped_rows_to_node[preload], groupby(it,lambda i:i[0])) # will work but having the next "if" is faster
    if preload & 2: return imap(self.__grouped_rows_to_node[preload], groupby(it,lambda i:i[0]))
    return imap(self.__row_to_node[preload], it)

  def descendantsIter(self,preload=WITH_CONTENT_AND_TAGS):
    """an iter retrieves all the children of this node, going deeper in a flat-fashion, pre-loading content and tags by default.

where preload can be:
  0  WITH_NONE
  1  WITH_CONTENT
  2  WITH_TAGS
  3  WITH_CONTENT_AND_TAGS
"""
    o1,o2=self.kitab.getSliceBoundary(self.idNum)
    if o2==-1: sql=SQL_GET_UNBOUNDED_NODES_SLICE[preload] ; args=(o1,)
    else: sql=SQL_GET_NODES_SLICE[preload]; args=(o1,o2)
    it=self.kitab.cn.execute(sql, args)
    # return imap(self.__grouped_rows_to_node[preload], groupby(it,lambda i:i[0])) # will work but having the next "if" is faster
    if preload & 2: return imap(self.__grouped_rows_to_node[preload], groupby(it,lambda i:i[0]))
    return imap(self.__row_to_node[preload], it)

  def childrenWithTagNameIter(self, tagname, load_content=True):
    """an iter that retrieves all direct children taged with tagname, just one level deeper"""
    it=self.kitab.cn.execute(SQL_GET_TAGGED_CHILD_NODES[load_content], (self.idNum,tagname))
    return imap(self.__row_to_node[load_content],it)

  def descendantsWithTagNameIter(self, tagname,load_content=True):
    """an iter that retrieves all the children idnum tagged with tagname, going deeper in a flat-fashion"""
    o1,o2=self.kitab.getSliceBoundary(self.idNum)
    if o2==-1: sql=SQL_GET_UNBOUNDED_TAGGED_NODES_SLICE[load_content]; args=(tagname,o1,)
    else: sql=SQL_GET_TAGGED_NODES_SLICE[load_content]; args=(tagname,o1,o2)
    it=self.kitab.cn.execute(sql, args)
    return imap(self.__row_to_node[load_content],it)

#  recursive non-optimized code
#  def traverser_(self, nodeStart, nodeEnd,preload=WITH_CONTENT_AND_TAGS,*args):
#    """recursively traverser nodes calling nodeStart and nodeEnd"""
#    nodeStart(self,*args)
#    for i in self.childrenIter(preload):
#      i.traverser_(nodeStart,nodeEnd,*args)
#    nodeEnd(self,*args)
  def traverser(self, preload, nodeStart, nodeEnd, *args):
    """recursively traverser nodes calling nodeStart and nodeEnd

Note: the implementation is a non-recursive optimized code with a single query"""
    dummy=lambda *args: None
    if not nodeStart: nodeStart=dummy
    if not nodeEnd: nodeEnd=dummy
    stack=[self]
    nodeStart(self,*args)
    for i in self.descendantsIter(preload):
      while(i.parent!=stack[-1].idNum): nodeEnd(stack[-1],*args); stack.pop()
      stack.append(i)
      nodeStart(i,*args)
    while(stack): nodeEnd(stack[-1],*args); stack.pop()

  def traverserWithStack(self, preload, nodeStart, nodeEnd, *args):
    """recursively traverser nodes calling nodeStart and nodeEnd passing the nodes stack to them

Note: the implementation is a non-recursive optimized code with a single query"""
    dummy=lambda *args: None
    if not nodeStart: nodeStart=dummy
    if not nodeEnd: nodeEnd=dummy
    stack=[self]
    nodeStart(stack,*args)
    for i in self.descendantsIter(preload):
      while(i.parent!=stack[-1].idNum): nodeEnd(stack,*args); stack.pop()
      stack.append(i)
      nodeStart(stack,*args)
    while(stack): nodeEnd(stack,*args); stack.pop()

  def sTraverser(self, preload, nodeStart, nodeEnd,*args):
    """recursively traverser nodes calling nodeStart and nodeEnd and concatenating the return values"""
    stack=[self]
    s=nodeStart(self,*args)
    for i in self.descendantsIter(preload):
      while(i.parent!=stack[-1].idNum): s+=nodeEnd(stack[-1],*args); stack.pop()
      s+=nodeStart(i,*args)
      stack.append(i)
    while(stack): s+=nodeEnd(stack[-1],*args); stack.pop()
    return s

  def toWiki(self):
    """export the node and its descendents into a wiki-like string"""
    return self.sTraverser( 3, lambda n: n.getTags().has_key('header') and ''.join((u'\n',((7-n.depth)*u'='),n.getContent(),((7-n.depth)*u'='),u'\n')) or n.getContent(), lambda n: u'');

  def toHTML(self):
    """export the node and its descendents into a wiki-like string"""
    # TODO: escape special chars
    # TODO: replace ^$ with '<br/>' or '</p><p>'
    return self.sTraverser( 3, lambda n: n.getTags().has_key('header') and u'\n<H%d>%s</H%d>\n' % (n.depth,escape(n.getContent()),n.depth) or escape(n.getContent()), lambda n: u'');


  def __toXmlStart(self, node, ostream):
    margin=u'  '*node.depth
    tags=u' '.join(map(lambda d: d[1]==None and d[0] or d[0]+u'='+quoteattr(unicode(d[1])) ,node.getTags().items()))
    ostream.write(u' '.join((margin,u'<Node',tags,u'><content>',)))
    ostream.write(escape(node.getContent()))
    ostream.write(u'</content>\n')
  def __toXmlEnd(self, node, ostream):
    margin=u'  '*node.depth
    ostream.write(margin+u' </Node>\n')
    
  def toXml(self,ostream):
    """export the node and its descendents into a wiki-like string using ostream as output"""
    # TODO: escape special chars
    self.traverser(3,self.__toXmlStart,self.__toXmlEnd,ostream)

#  def toXml(self,ostream):
#    # fixme
#    margin=u'  '*self.depth
#    tags=u' '.join(map(lambda d: d[1]==None and d[0] or d[0]+u'='+unicode(d[1]) ,self.getTags().items()))
#    ostream.write(u' '.join((margin,u'<Node',tags,u'>\n',)))
#    ostream.write(self.getContent())
#    for i in descendantsIter():
#      margin=u'  '*i.depth
#      tags=u' '.join(map(lambda d: d[1]==None and d[0] or d[0]+u'='+unicode(d[1]) ,i.getTags().items()))
#      ostream.write(u' '.join((margin,u'<Node',tags,u'>\n',)))
#      ostream.write(i.getContent())
#      ostream.write(u'\n'+margin+u' </Node>\n')
#    ostream.write(u'\n'+margin+u' </Node>\n')

####################################

if __name__ == '__main__':
  th=ThawabMan(os.path.expanduser('~/.thawab'))
  ki=th.mktemp()
  wiki=open(wiki_filename,"r")
  ki.seek(-1,-1)
  wiki2th(ki,wiki)
  ki.flush()

