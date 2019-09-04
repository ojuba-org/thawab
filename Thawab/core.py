# -*- coding: UTF-8 -*-
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
import sys, os, os.path, sqlite3, re
import threading
from glob import glob
from itertools import groupby
from tempfile import mkstemp
from io import StringIO
from xml.sax.saxutils import escape, unescape, quoteattr # for xml rendering
from .dataModel import *
from .tags import *
from .meta import MCache, metaDict2Hash, prettyId, makeId, metaVrr
from .userDb import UserDb
from .platform import guess_prefixes

from .whooshSearchEngine import SearchEngine
from .asyncIndex import AsyncIndex
from othman.core import othmanCore
from okasha.utils import ObjectsCache, fromFs, toFs
from functools import reduce

th_ext = '.ki'
th_ext_glob = '*.ki'
othman = othmanCore()

class ThawabMan (object):
    def __init__(self, prefixes=None, isMonolithic = True, indexerQueueSize = 0):
        """Create a new Thawab instance given a user writable directory and an optional system-wide read-only directory

    prefixes a list of directories all are read-only except the first
    the first writable directory can be 
        os.path.expanduser('~/.thawab')
        os.path.join([os.path.dirname(sys.argv[0]),'..','data'])
    
    isMonolithic = True if we should use locks and reconnect to sqlite
    
    indexerQueueSize is the size of threaded index queue (0 infinite, -1 disabled)

the first thing you should do is to call loadMCache()
"""
        if not prefixes:
            prefixes = guess_prefixes()
        try:
            if not os.path.isdir(prefixes[0]):
                os.makedirs(prefixes[0])
        except:
            raise OSError
        self.prefixes = [i for i in [os.path.realpath(os.path.abspath(p)) for p in prefixes] if os.path.isdir(i)]
        # make sure it's unique
        p = self.prefixes[0]
        s = set(self.prefixes[1:])
        if p in s:
            s.remove(p)
        if len(s)<len(self.prefixes)-1:
            self.prefixes=[p]+sorted(list(s))
        #print self.prefixes
        self.othman = othman
        self.__meta = None
        self.read_only = self.assertManagedTree()
        self.conf = self.prase_conf()
        self.searchEngine = SearchEngine(self)
        self.user_db = UserDb(self, os.path.join(self.prefixes[0], "user.db"))
        if indexerQueueSize >= 0:
            self.asyncIndexer = AsyncIndex(self.searchEngine, indexerQueueSize)
        else:
            self.asyncIndexer = None

        self.isMonolithic = isMonolithic
        if not self.isMonolithic:
            import threading
            lock1 = threading.Lock()
        else:
            lock1 = None
        self.kutubCache = ObjectsCache(lock = lock1)

    def prase_conf(self):
        r = {}
        fn = os.path.join(self.prefixes[0], 'conf', 'main.txt')
        if not os.path.exists(fn):
            return {}
        try:
            f = open(fn)
            t = f.readlines()
            f.close()
        except:
            return {}
        for l in t:
            a = l.strip().split(" = ",1)
            if len(a) != 2:
                continue
            r[a[0].strip()] = a[1].strip()
        return r

    def assertManagedTree(self):
         """create the hierarchy inside the user-managed prefix        
         # db    contains Kitab files [.thawab]
         # index    contains search index
         # conf    application configuration
         # cache    contains the metadata cache for all containers"""
         P = self.prefixes[0]
         if not os.access(P, os.W_OK):
            return False
         for i in ['db','index','conf','cache', 'tmp', 'themes']:
             p = os.path.join(P,i)
             if not os.path.isdir(p):
                os.makedirs(p)
         return True

    def mktemp(self):
        h, fn = mkstemp(th_ext, 'THAWAB_' ,os.path.join(self.prefixes[0], 'tmp'))
        return Kitab(fn, True)

    def getCachedKitab(self, uri):
        """
        try to get a kitab by uri from cache,
        if it's not in the cache, it will be opened and cached
        """
        ki = self.kutubCache.get(uri)
        if not ki:
            ki = self.getKitabByUri(uri)
            if ki:
                self.kutubCache.append(uri, ki)
        #elif not self.isMonolithic: ki.connect() # FIXME: no longer needed, kept to trace other usage of isMonolithic
        return ki

    def getCachedKitabByNameV(self, kitabNameV):
        a = kitabNameV.split('-')
        l = len(a)
        if l == 1:
            m = self.getMeta().getLatestKitab(kitabNameV)
        elif l == 2:
            m = self.getMeta().getLatestKitabV(*a)
        else:
            m = self.getMeta().getLatestKitabVr(*a)
        if m:
            return self.getCachedKitab(m['uri'])
        return None

    def getUriByKitabName(self,kitabName):
        """
        return uri for the latest kitab with the given name
        """
        m = self.getMeta().getLatestKitab(kitabName)
        if not m:
            return None
        return m['uri']

    def getKitab(self,kitabName):
        m = self.getMeta().getLatestKitab(kitabName)
        if m:
            return Kitab(m['uri'], th = self, meta = m)
        return None

    def getKitabByUri(self,uri):
        m = self.getMeta().getByUri(uri)
        if m:
            return Kitab(uri, th = self, meta = m)
        return Kitab(uri, th=self)

    def getKitabList(self):
        """
        return a list of managed kitab's name
        """
        return self.getMeta().getKitabList()

    def getManagedUriList(self):
        """list of all managed uri (absolute filenames for a Kitab)
         this is low level as the user should work with kitabName, title, and rest of meta data"""
        if self.__meta:
            return self.__meta.getUriList()
        r = []
        for i in self.prefixes:
            a = glob(toFs(os.path.join(fromFs(i),'db',th_ext_glob)))
            p = [fromFs(j) for j in a]
            r.extend(p)
        return r

    def getMeta(self):
        if not self.__meta:
            self.loadMeta()
        return self.__meta

    def loadMeta(self):
        self.__meta = None
        p = os.path.join(self.prefixes[0],'cache','meta.db')
        self.__meta = MCache(p, self.getManagedUriList())
        return self.__meta

    def reconstructMetaIndexedFlags(self):
        # NOTE: getMeta is not used because we want to make sure we are using a fresh one
        m = self.loadMeta() 
        l1 = m.getIndexedList()
        l2 = m.getUnindexedList()
        # NOTE: Dirty are kept as is
        #l3 = m.getDirtyIndexList() 
        for i in l1:
            v = self.searchEngine.getIndexedVersion(i['kitab'])
            # mark as unindexed
            if not v or metaVrr(i) != v:
                m.setIndexedFlags(i['uri'], 0) 
        for i in l2:
            v = self.searchEngine.getIndexedVersion(i['kitab'])
            if v and metaVrr(i) == v:
                # mark as indexed if same version
                m.setIndexedFlags(i['uri']) 

class KitabCursor:
    """
    an object used to do a sequence of SQL operation
    """
    def __init__(self, ki , *args, **kw):
        self.ki = ki
        self.__is_tailing = False
        self.__is_tmp = False
        self.__tmp_str = ''
        self.__parents=[]
        self.__c = None
        self.__last_go = -1
        if args or kw:
            self.seek(*args, **kw)
        
    def __lock(self):
        # TODO: this is just a place holders, could be used to do "BEGIN TRANS"
        pass

    def __unlock(self):
        pass

    def seek(self, parentNodeIdNum = -1,nodesNum = -1):
        """
            should be called before concatenating nodes, all descendants will be dropped
            where:
                parentNodeIdNum    - the parent below which the concatenation will begin, -1 at the tail
                nodesNum        - number of nodes to be concatenated, -1 for unknown open number

            seek()
            appendNode(parentNodeIdNum, content, tags)
            appendNode(parentNodeIdNum, content, tags)
            ...
            plush()
        """
        self.__lock()
        self.__is_tailing = False
        self.__is_tmp = False
        self.__tmp_str = ''
        self.__parents = []
        self.__c = self.ki.cn().cursor()
        self.__c.execute('BEGIN TRANSACTION')
        if parentNodeIdNum != -1:
            self.dropDescendants(parentNodeIdNum)
            if nodesNum == -1:
                self.__is_tmp = True
                self.__tmp_str = 'tmp'
            else:
                # FIXME: make sure 
                raise IndexError("not implented")
        else:
            self.__parents = [self.ki.root]
            r = self.__c.execute(SQL_GET_LAST_GLOBAL_ORDER).fetchone()
            if r:
                self.__last_go = r[0]
            else:
                self.__last_go = 0
            self.__is_tailing = True

    def flush(self):
        """Called after the last appendNode"""
        if self.__is_tmp:
            # TODO: implement using "insert into ... select tmp_nodes ...;"
            raise IndexError("not implented")
        self.__c.execute('END TRANSACTION')
        #self.__c.execute('COMMIT')
        #self.ki.cn.commit() # FIXME: is this needed ?
        self.__unlock()

    def appendNode(self, parentNode, content, tags):
        parentNodeIdNum = parentNode.idNum
        while(self.__parents[-1].idNum != parentNodeIdNum):
            self.__parents.pop()
        new_go = self.__last_go + self.ki.inc_size
        newid = self.__c.execute(SQL_APPEND_NODE[self.__is_tmp],
                                 (content,
                                  self.__parents[-1].idNum,
                                  new_go,
                                  self.__parents[-1].depth + 1)).lastrowid
        self.__last_go = new_go
        node = Node(kitab = self.ki,
                    idNum = newid,
                    parent = self.__parents[-1].idNum,
                    depth = self.__parents[-1].depth + 1)
        node.applyTags(tags)
        self.__parents.append(node)
        return node

    def dropDescendants(self,parentNodeIdNum, withParent = False):
        """remove all child nodes going deep at any depth, and optionally with their parent"""
        o1, o2 = self.ki.getSliceBoundary(parentNodeIdNum)
        c = self.__c
        if not c:
            c = self.ki.cn().cursor()
        if o2 == -1:
            c.execute(SQL_DROP_TAIL_NODES[withParent],(o1,))
        else:
            c.execute(SQL_DROP_DESC_NODES[withParent],(o1,o2))

class Kitab(object):
    """this class represents a book or an article ...etc."""
    def __init__(self,uri, is_tmp = False, th = None, meta = None):
        """
        open the Kitab pointed by uri (or try to create it)
        is_tmp should be set to True when we are creating a new kitab from scratch in temporary 
        th is ThawabManaget to which this book belongs
        meta is meta cache entry of this kitab
        
        Note: don't rely on meta having uri, mtime, flags unless th is set (use uri property instead)
        """
        self._cn_h = {} # per-thread sqlite connection
        # node generators
        self.grouped_rows_to_node = (self.grouped_rows_to_node0,
                                     self.grouped_rows_to_node1,
                                     self.grouped_rows_to_node2,
                                     self.grouped_rows_to_node3)
        self.row_to_node = (self.row_to_node0, self.row_to_node1)
        # TODO: do we need a mode = r|w ?
        self.uri = uri
        self.is_tmp = is_tmp
        self.th = th
        self.meta = meta
        if not meta: self.getMCache()
        if meta and meta.get('originalKitab',None):
            self.originalKi = self.th.getCachedKitabByNameV(meta['originalKitab'] + \
                                                            "-" + \
                                                            meta['originalVersion'])
        else: self.originalKi = None
        # the logic to open the uri goes here
        # check if fn exists, if not then set the flag sql_create_schema
        if is_tmp or not os.path.exists(toFs(uri)):
            sql_create_schema = True
        else:
            sql_create_schema = False
        cn = self.cn()
        # FIXME: do we really need this
        cn.create_function("th_enumerate", 0, self.rowsEnumerator) 
        # NOTE: we have a policy, no saving of cursors in object attributes for thread safty
        c = cn.cursor()
        self.toc = KitabToc(self)
        # private
        self.__tags = {} # a hash by of tags data by tag name
        self.__tags_loaded = False
        self.__counter = 0 # used to renumber rows
        self.inc_size = 1 << 10
        # TODO: make a decision, should the root node be saved in SQL,
        # if so a lower bound checks to Kitab.getSliceBoundary() and an exception into Kitab.getNodeByIdNum()
        self.root = Node(kitab = self,
                         idNum = 0,
                         parent = -1,
                         depth = 0,
                         content = '',
                         tags = {})
        if sql_create_schema:
            c.executescript(SQL_DATA_MODEL)
            # create standard tags
            for t in STD_TAGS_ARGS:
                c.execute(SQL_ADD_TAG, t)

    def cn(self):
        """
        return an sqlite connection for the current thread
        """
        n = threading.current_thread().name
        if n in self._cn_h:
            r = self._cn_h[n]
        else:
            r = sqlite3.connect(self.uri, isolation_level = None)
            self._cn_h[n] = r
        return r

    def getMCache(self):
        if not self.th:
            return None # needs a manager
        if self.meta:
            return self.meta
        self.meta = self.th.getMeta().load_from_uri(self.uri)
        return self.meta

    def setMCache(self, meta):
        # TODO: add more checks
        a = meta.get('author', None)
        oa = meta.get('originalAuthor', None)
        if not oa and not a:
            meta['author'] = '_unset'
        if not a and oa != None:
            meta['author'] = oa
        if not oa and a != None:
            meta['originalAuthor'] = a
        y = meta.get('year', None)
        oy = meta.get('originalYear', None)
        if not y and oy != None:
            meta['year'] = oy
        if not oy and y != None:
            meta['originalYear'] = y
        if not meta.get('cache_hash',None):
            meta['cache_hash'] = metaDict2Hash(meta)
        self.meta = meta
        self.cn().execute(SQL_MCACHE_SET, meta)

    ###################################
    # retrieving data from the Kitab
    ###################################
    def getTags(self):
        if not self.__tags_loaded:
            self.reloadTags()
        return self.__tags
    
    def reloadTags(self):
        self.__tags = dict([(r[0],r[1:]) for r in self.cn().execute(SQL_GET_ALL_TAGS).fetchall()])
        self.__tags_loaded = True

    def getNodeByIdNum(self, idNum, load_content = False):
        if idNum <= 0:
            return self.root
        r = self.cn().execute(SQL_GET_NODE_BY_IDNUM[load_content],
                              (idNum,)).fetchone()
        if not r:
            raise IndexError("idNum not found")
        return self.row_to_node[load_content](r)

    def getNodesByTagValueIter(self, tagname, value, load_content = True, limit = 0):
        """an iter that retrieves all the modes tagged with tagname having value"""
        sql = SQL_GET_NODES_BY_TAG_VALUE[load_content]
        if type(limit) == int and limit > 0:
            sql + " LIMIT " + str(limit)
        it = self.cn().execute(sql, (tagname, value,))
        return map(self.row_to_node[load_content], it)

    def nodeFromId(self, i, load_content = False):
        """
        get node from Id where is is one of the following:
            * an intger (just call getNodeByIdNum)
            * a string prefixed with "_i" followed by IdNum
            * the value of "header" param
        """
        if type(i) == int:
            j = i
            return self.getNodeByIdNum(j, load_content)
        elif i.startswith('_i'):
            try:
                j = int(i[2:])
            except TypeError:
                return None
            return self.getNodeByIdNum(j, load_content)
        else:
            nodes = self.getNodesByTagValueIter("header", i, load_content, 1)
            if nodes: return nodes[0]
        return None

    def seek(self, *args, **kw):
        """
        short hand for creating a cursor object and seeking it, returns a new cursor object used for manipulation ops
        """
        return KitabCursor(self, *args, **kw)

    def getSliceBoundary(self, nodeIdNum):
        """return a tuble of o1,o2 where:
            o1: is the globalOrder of the given Node
            o2: is the globalOrder of the next sibling of the given node, -1 if unbounded
all the descendants of the given nodes have globalOrder belongs to the interval (o1,o2)
        """
        # this is a private method used by dropDescendants
        if nodeIdNum == 0:
            return 0,-1
        cn = self.cn()
        r = cn.execute(SQL_GET_GLOBAL_ORDER,(nodeIdNum,)).fetchone()
        if not r:
            raise IndexError
        o1 = r[0]
        depth = r[1]
        r = cn.execute(SQL_GET_DESC_UPPER_BOUND, (o1, depth)).fetchone()
        if not r:
            o2 = -1
        else:
            o2 = r[0]
        return o1, o2

    # node generators
    def row_to_node0(self,r):
        return Node(kitab=self,
                    idNum = r[0],
                    parent = r[1],
                    depth = r[2],
                    globalOrder = r[3])

    def row_to_node1(self,r):
        return Node(kitab=self,
                    idNum = r[0],
                    parent = r[1],
                    depth = r[2],
                    globalOrder = r[3],
                    content = r[4])

    def grouped_rows_to_node0(self,l):
        r = list(l[1])
        return Node(kitab=self,
                    idNum = r[0][0],
                    parent = r[0][1],
                    depth = r[0][2],
                    globalOrder = r[0][3])

    def grouped_rows_to_node1(self,l):
        r = list(l[1])
        return Node(kitab=self,
                    idNum = r[0][0],
                    parent = r[0][1],
                    depth = r[0][2],
                    globalOrder = r[0][3],
                    content = r[0][4])

    def grouped_rows_to_node2(self,l):
        r = list(l[1])
        return Node(kitab=self.kitab,
                    idNum = r[0][0],
                    parent = r[0][1],
                    depth = r[0][2],
                    globalOrder = r[0][3],
                    tags = dict([(i[4],i[5]) for i in r]),
                    tag_flags = reduce(lambda a,b: a|b[6],r,0))

    def grouped_rows_to_node3(self,l):
        r = list(l[1])
        return Node(kitab=self,
                    idNum = r[0][0],
                    parent = r[0][1],
                    depth = r[0][2],
                    globalOrder = r[0][3],
                    content = r[0][4],
                    tags = dict([(i[5],i[6]) for i in r]),
                    tag_flags = reduce(lambda a,b: a|b[7],r, 0))

    def getChildNodesIter(self, idNum, preload = WITH_CONTENT_AND_TAGS):
        """
            an iter that retrieves all direct children of a node by its IdNum,
            just one level deeper, content and tags will be pre-loaded by default.

            where preload can be:
                0    WITH_NONE
                1    WITH_CONTENT
                2    WITH_TAGS
                3    WITH_CONTENT_AND_TAGS
        """
        it = self.cn().execute(SQL_GET_CHILD_NODES[preload],(idNum,))
        # will work but having the next "if" is faster
        # return imap(self.grouped_rows_to_node[preload], groupby(it,lambda i:i[0]))
        if preload & 2:
            return map(self.grouped_rows_to_node[preload],
                        groupby(it,lambda i:i[0]))
        return map(self.row_to_node[preload], it)

    def getTaggedChildNodesIter(self, idNum, tagName, load_content = True):
        """
            an iter that retrieves all direct children of a node having tagName by its IdNum,
            just one level deeper, content will be preloaded by default.
        """
        it = self.cn().execute(SQL_GET_TAGGED_CHILD_NODES[load_content], (idNum,tagName,))
        return map(self.row_to_node[load_content], it)


    # FIXME: do we really need this
    def rowsEnumerator(self):
        """private method used internally"""
        self.__counter += self.inc_size
        return self.__counter

class KitabToc(object):
    def __init__(self, kitab):
        self.ki = kitab

    def breadcrumbs(self, node):
        l = []
        n = node
        p = self.ki.getNodeByIdNum(n.parent, True)
        while(p.idNum):
            # TODO: do some kind of cache like this if p.idNum in cache: l = cached + l else: ...
            l.insert(0, (p.idNum, p.getContent()))
            p = self.ki.getNodeByIdNum(p.parent, True)
        return l

    def getNodePrevUpNextChildrenBreadcrumbs(self, i):
        """
            an optimized way to get a tuple of node, prev, up, next, children, breadcrumbs
            where i is nodeIdNum or preferably the node it self
        """
        if type(i) == int:
            n = self.ki.getNodeByIdNum(i, True)
        elif isinstance(i,str):
            n = self.ki.nodeFromId(i, True)
        else:
            n = i
        return (n,
                self.prev(n),
                self.ki.getNodeByIdNum(n.parent, True),
                self.next(n),
                self.children(n.idNum),
                self.breadcrumbs(n))

    def children(self, i):
        """
        return list of Node that are direct children of i
        where i is idNum of the node
        """
        return list(self.ki.getTaggedChildNodesIter(i, 'header', True))

    def up(self, i):
        if type(i) == int:
            n = self.ki.getNodeByIdNum(i, True)
        else:
            n = i
        return self.ki.getNodeByIdNum(n.parent, True)

    def prev(self, i):
        if type(i) == int:
            n = self.ki.getNodeByIdNum(i, True)
        else:
            n = i
        return n.getPrevTaggedNode('header')

    def next(self, i):
        if type(i) == int:
            n = self.ki.getNodeByIdNum(i, True)
        else:
            n = i
        return n.getNextTaggedNode('header')

class Node (object):
    """
        A node class returned by some Kitab methods, avoid creating your own

        it has the following properities:
            kitab            the Kitab instance to which this node belonds, none if floating
            parent        the parent node idNum, -1 if root
            idNum            the node idNum, -1 if floating or not yet saved
            depth            the depth of node, -1 for floating, 0 for root
            tags            the applied tags, {tagname:param,...}, None if not loaded
        and the following methods:
            getContent()        return node's content, loading it from back-end if needed
            reloadContent()    force reloading content
            unloadContent()    unload content to save memory
    """
    _footnote_s_re = re.compile(r'(\^\[([^\[\]]+)\])', re.M)
    _footnote_t_re = re.compile(r'^(    \* *\(([^\(\)]+)\))', re.M)
    _href_named_re = re.compile(r'\[\[([^ \[\]]+) ([^\[\]]+)\]\]', re.M)
    _href_re = re.compile(r'\[\[([^ \[\]]+)\]\]', re.M)
    def __init__(self, **args):
        self.kitab = args.get('kitab')
        self.parent = args.get('parent', -1)
        self.idNum = args.get('idNum', -1)
        self.depth = args.get('depth', -1)
        self.globalOrder = args.get('globalOrder', -1)

        # TODO: should globalOrder be a properity ?
        try:
            self.__content = args['content']
            self.__content_loaded = True
        except KeyError:
            self.__content_loaded = False
        # TODO: should tags be called tagDict
        try:
            self.__tags=args['tags']
            self.__tags_loaded = True
        except KeyError:
            self.__tags_loaded = False
        try:
            self.__tag_flags = args['tag_flags']
            self.__tag_flags_loaded = True
        except KeyError:
            self.__tag_flags_loaded = False

    # tags related methods
    def getTags(self):
        """
            return tag dictionary applied to the node, loading it from back-end if needed
        """
        if not self.__tags_loaded:
            self.reloadTags()
        return self.__tags
    
    def getTagFlags(self):
        """
            return the "or" summation of flags of all tags applied to this node
        """
        if not self.__tag_flags_loaded:
            self.reloadTags()
        return self.__tag_flags

    def getTagsByFlagsMask(self, mask):
        """
            return tag names having flags masked with mask,
            used like this node.getTagsByFlagsMask(TAG_FLAGS_IX_TAG)
        """
        # return filter(lambda t: STD_TAGS_HASH[t][2]&mask, self.getTags())
        return [t for t in self.getTags() if self.kitab.getTags()[t][0]&mask]
    
    def reloadTags(self):
        """force reloading of Tags"""
        self.__tags = dict(self.kitab.cn().execute(SQL_GET_NODE_TAGS,(self.idNum,)).fetchall())
        self.__tags_loaded = True
        T = [self.kitab.getTags()[t][0] for t in list(self.__tags.keys())]
        self.__tag_flags = reduce(lambda a,b: a|b,T, 0)
        self.__tag_flags_loaded = True
        
    def unloadTags(self):
        """unload content to save memory"""
        self.__tags_loaded = False
        self.__tags = None
        self.__tag_flags = 0
        self.__tag_flags_loaded = False
    # content related methods
    
    def getContent(self):
        """return node's content, loading it from back-end if needed"""
        if not self.__content_loaded:
            self.reloadContent()
        return self.__content
    
    def reloadContent(self):
        """force reloading content"""
        r = self.kitab.cn().execute(SQL_GET_NODE_CONTENT,(self.idNum,)).fetchone()
        if not r:
            self.__content = None
            self.__content_loaded = False
            raise IndexError('node not found, could be a floating node')
        self.__content = r[0]
        self.__content_loaded = True
    
    def unloadContent(self):
        """unload content to save memory"""
        self.__content_loaded = False
        self.__content = None
    
    # tags editing
    def tagWith(self,tag,param = None):
        """
            apply a single tag to this node,
            if node is already taged with it, just update the param
            the tag should already be in the kitab.
        """
        r = self.kitab.cn().execute(SQL_TAG,(self.idNum,param,tag)).rowcount
        if not r:
            raise IndexError("tag not found")

    def applyTags(self,tags):
        """
            apply a set of taga to this node,
            if node is already taged with them, just update the param
            each tag should already be in the kitab.
        """
        for k in tags:
            self.tagWith(k, tags[k])
    def clearTags(self):
        """clear all tags applyed to this node"""
        self.kitab.cn().execute(SQL_CLEAR_TAGS_ON_NODE, (self.idNum,))

    def getPrevTaggedNode(self, tagName, load_content = True):
        if self.idNum <= 0:
            return None
        r = self.kitab.cn().execute(SQL_GET_PREV_TAGGED_NODE[load_content],
                                    (self.globalOrder, tagName)).fetchone()
        if not r:
            return None
        return self.kitab.row_to_node[load_content](r)

    def getNextTaggedNode(self, tagName, load_content = True):
        r = self.kitab.cn().execute(SQL_GET_NEXT_TAGGED_NODE[load_content],
                                    (self.globalOrder, tagName)).fetchone()
        if not r:
            return None
        return self.kitab.row_to_node[load_content](r)

    # methods that give nodes
    def childrenIter(self, preload = WITH_CONTENT_AND_TAGS):
        """
            an iter that retrieves all direct children of this node,
            just one level deeper, content and tags will be pre-loaded by default.

            where preload can be:
                0    WITH_NONE
                1    WITH_CONTENT
                2    WITH_TAGS
                3    WITH_CONTENT_AND_TAGS
        """
        return self.kitab.nodeChildrenIter(self.idNum, preload)

    def descendantsIter(self,preload = WITH_CONTENT_AND_TAGS, upperBound = -1):
        """
            an iter retrieves all the children of this node,
            going deeper in a flat-fashion, pre-loading content and tags by default.

            where preload can be:
                0    WITH_NONE
                1    WITH_CONTENT
                2    WITH_TAGS
                3    WITH_CONTENT_AND_TAGS
        """
        o1, o2 = self.kitab.getSliceBoundary(self.idNum)
        if upperBound != -1 and (o2 == -1 or o2 > upperBound):
            o2 = upperBound
        if o2 == -1:
            sql = SQL_GET_UNBOUNDED_NODES_SLICE[preload]
            args = (o1,)
        else:
            sql = SQL_GET_NODES_SLICE[preload]
            args = (o1, o2)
        it = self.kitab.cn().execute(sql, args)
        # will work but having the next "if" is faster
        # return imap(self.kitab.grouped_rows_to_node[preload], groupby(it,lambda i:i[0])) 
        if preload & 2:
            return map(self.kitab.grouped_rows_to_node[preload],
                        groupby(it, lambda i:i[0]))
        return map(self.kitab.row_to_node[preload], it)

    def childrenWithTagNameIter(self, tagname, load_content = True):
        """
            an iter that retrieves all direct children taged with tagname, just one level deeper
        """
        it = self.kitab.cn().execute(SQL_GET_TAGGED_CHILD_NODES[load_content],
                                     (self.idNum, tagname))
        return map(self.kitab.row_to_node[load_content], it)

    def descendantsWithTagNameIter(self, tagname,load_content = True):
        """
            an iter that retrieves all the children tagged with tagname,
            going deeper in a flat-fashion
        """
        o1, o2 = self.kitab.getSliceBoundary(self.idNum)
        if o2 == -1:
            sql = SQL_GET_UNBOUNDED_TAGGED_NODES_SLICE[load_content]
            args=(tagname, o1,)
        else:
            sql = SQL_GET_TAGGED_NODES_SLICE[load_content]
            args=(tagname, o1, o2)
        it = self.kitab.cn().execute(sql, args)
        return map(self.kitab.row_to_node[load_content], it)



#    recursive non-optimized code
#    def traverser_(self, nodeStart, nodeEnd,preload = WITH_CONTENT_AND_TAGS,*args):
#        """recursively traverser nodes calling nodeStart and nodeEnd"""
#        nodeStart(self,*args)
#        for i in self.childrenIter(preload):
#            i.traverser_(nodeStart,nodeEnd,*args)
#        nodeEnd(self,*args)
    def traverser(self, preload, nodeStart, nodeEnd, *args):
        """
            recursively traverser nodes calling nodeStart and nodeEnd

            Note: the implementation is a non-recursive optimized code with a single query
        """
        dummy = lambda *args: None
        if not nodeStart:
            nodeStart = dummy
        if not nodeEnd:
            nodeEnd = dummy
        stack = [self]
        nodeStart(self, *args)
        for i in self.descendantsIter(preload):
            while(i.parent != stack[-1].idNum):
                nodeEnd(stack[-1], *args)
                stack.pop()
            stack.append(i)
            nodeStart(i, *args)
        while(stack):
            nodeEnd(stack[-1], *args)
            stack.pop()

    def traverserWithStack(self, preload, nodeStart, nodeEnd, *args):
        """
            recursively traverser nodes calling nodeStart
            and nodeEnd passing the nodes stack to them

            Note: the implementation is a non-recursive optimized code with a single query
        """
        dummy = lambda *args: None
        if not nodeStart:
            nodeStart = dummy
        if not nodeEnd:
            nodeEnd = dummy
        stack = [self]
        nodeStart(stack, *args)
        for i in self.descendantsIter(preload):
            while(i.parent != stack[-1].idNum):
                nodeEnd(stack, *args)
                stack.pop()
            stack.append(i)
            nodeStart(stack, *args)
        while(stack):
            nodeEnd(stack, *args)
            stack.pop()

    def sTraverser(self, preload, nodeStart, nodeEnd,upperBound = -1, *args):
        """
            recursively traverser nodes calling nodeStart and nodeEnd
            and concatenating the return values
        """
        stack = [self]
        s = nodeStart(self, *args)
        for i in self.descendantsIter(preload, upperBound):
            while(i.parent != stack[-1].idNum):
                s += nodeEnd(stack[-1],*args)
                stack.pop()
            s += nodeStart(i, *args)
            stack.append(i)
        while(stack):
            s += nodeEnd(stack[-1], *args)
            stack.pop()
        return s

    def toWiki(self):
        """export the node and its descendants into a wiki-like string"""
        return self.sTraverser(3,
                               lambda n: 'header' in n.getTags() and \
                               ''.join(('\n',
                                        ((7-n.depth)*' = '),
                                        n.getContent(),
                                        ((7-n.depth)*' = '),'\n')) or \
                                        n.getContent(),
                               lambda n: '')

    def toHtml_cb(self, n):
        # trivial implementation
        #return n.getTags().has_key('header') and \
        #        u'\n<H%d>%s</H%d>\n' % (n.depth,escape(n.getContent()),n.depth) or \
        #        "<p>%s</p>" % escape(n.getContent())
        r = ""
        if 'header' in n.getTags():
            r = '\n<H%d>%s</H%d>\n' % (n.depth, escape(n.getContent()), n.depth)
        else:
            r = "<p>%s</p>" % self._wiki2html(escape(n.getContent()))
        if 'quran.tafseer.ref' in n.getTags():
            sura,aya,na = n.getTags()['quran.tafseer.ref'].split('-')
            #r += u'<p class="quran">نص من القرآن %s:%s:%s</p>\n\n' % (sura,aya,na)
            # tanween fix u'\u064E\u064E', u'\u064E\u200C\u064E'
            r += '<p class="quran">%s</p>\n\n' % \
                 "".join([(i[0] + '\u202C').replace(' \u06dd',
                                                                  ' \u202D\u06dd') for i in othman.getAyatIter(othman.ayaIdFromSuraAya(int(sura),
                                    int(aya)),
                                    int(na))])
        if n.kitab and n.kitab.th:
            if n.kitab.originalKi and 'embed.original.section' in n.getTags():
                xref = n.getTags()['embed.original.section']
                matnKi = n.kitab.originalKi
                embd_class="quote_orignal"
                embd = "تعليقا على"
            elif 'embed.section.ref' in n.getTags():
                try:
                    matn, xref = n.getTags()['embed.section.ref'].split('/', 1)
                except ValueError:
                    pass
                else:
                    matnKi = n.kitab.th.getCachedKitabByNameV(matn)
                    embd_class = "quote_external"
                    embd = "اقتباس"
            else:
                embd = None
            if embd:
                matnNode = list(matnKi.getNodesByTagValueIter("header", xref, False, 1))
                if matnNode:
                    matnNode = matnNode[0]
                    s = '<blockquote class="%s"><p>%s:</p>' % (embd_class, embd)
                    nx = matnKi.toc.next(matnNode)
                    if nx:
                        ub = nx.globalOrder
                    else:
                        ub = -1
                    # pass an option to disable embed to avoid endless recursion
                    s += matnNode.toHtml(upperBound = ub) 
                    s += '<p>&nbsp;&nbsp;&nbsp;&nbsp;-- من كتاب <a href = "/view/%s/#%s" target = "_blank">%s</a></p>' % (matnKi.meta['kitab'],"_i"+str(matnNode.idNum),prettyId(matnKi.meta['kitab']))
                    s += '</blockquote>'
                    r += s
        return r

    def _wiki2html(self, txt):
        # TODO: split from "^__________$"
        # FIXME: when an embedded quoted section got footnotes there would be duplicated ids
        txt = self._footnote_s_re.sub(r'''<sup id = "fns_\2"><a href = "javascript:document.getElementById('fnt_\2').scrollIntoView();">(\2)</a></sup>''', txt)
        txt = self._footnote_t_re.sub(r'''<a id = "fnt_\2" href = "javascript:document.getElementById('fns_\2').scrollIntoView();">(\2)</a>''', txt)
        txt = self._href_named_re.sub(r'''<a class="external" href = "\1" target = "_blank">\2</a>''', txt)
        txt = self._href_re.sub(r'''<a class="external" href = "\1" target = "_blank">\1</a>''', txt)
        return txt

    def toHtml(self, upperBound = -1):
        """export the node and its descendants into HTML string"""
        # TODO: escape special chars
        # TODO: replace ^$ with '<br/>' or '</p><p>'
        # trivial implementation
        #return self.sTraverser( 3, lambda n: n.getTags().has_key('header') and u'\n<H%d>%s</H%d>\n' % (n.depth,escape(n.getContent()),n.depth) or "<p>%s</p>" % escape(n.getContent()), lambda n: u'', upperBound);
        return self.sTraverser( 3, self.toHtml_cb, lambda n: '', upperBound);

    def toText(self, upperBound = -1):
        """
        export node and its descendants into plain text string,
        can be used for generating excerpts of search results
        """
        return self.sTraverser( 3, lambda n: n.getContent(), lambda n: '', upperBound);

    def __toXmlStart(self, node, ostream):
        margin = '    '*node.depth
        tags=' '.join([d[1] == None and \
                                     d[0] or \
                                     d[0] + ' = ' + quoteattr(str(d[1])) for d in list(node.getTags().items())])
        ostream.write(' '.join((margin, '<Node', tags, '><content>',)))
        ostream.write(escape(node.getContent()))
        ostream.write('</content>\n')
    
    def __toXmlEnd(self, node, ostream):
        margin = '    ' * node.depth
        ostream.write(margin + ' </Node>\n')
        
    def toXml(self,ostream):
        """
            export the node and its descendants into a xml-like string using ostream as output
        """
        # TODO: escape special chars
        self.traverser(3, self.__toXmlStart, self.__toXmlEnd,ostream)

#    def toXml(self,ostream):
#        # fixme
#        margin = u'    '*self.depth
#        tags=u' '.join(map(lambda d: d[1] == None and d[0] or d[0]+u' = '+unicode(d[1]) ,self.getTags().items()))
#        ostream.write(u' '.join((margin,u'<Node',tags,u'>\n',)))
#        ostream.write(self.getContent())
#        for i in descendantsIter():
#            margin = u'    '*i.depth
#            tags=u' '.join(map(lambda d: d[1] == None and d[0] or d[0]+u' = '+unicode(d[1]) ,i.getTags().items()))
#            ostream.write(u' '.join((margin,u'<Node',tags,u'>\n',)))
#            ostream.write(i.getContent())
#            ostream.write(u'\n'+margin+u' </Node>\n')
#        ostream.write(u'\n'+margin+u' </Node>\n')
####################################

if __name__  ==  '__main__':
    th = ThawabMan(os.path.expanduser('~/.thawab'))
    ki = th.mktemp()
    wiki = open(wiki_filename, "r")
    ki.seek(-1, -1)
    wiki2th(ki, wiki)
    ki.flush()

