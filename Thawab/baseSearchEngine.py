# -*- coding: UTF-8 -*-
"""

Copyright © 2009, Muayyad Alsadi <alsadi@ojuba.org>

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
from meta import metaVrr
from okasha.utils import strverscmp
from tags import *

# TODO: use flags in meta cache object to indicate if indexing was started for some kitab so that if something wrong happend while indexing we can drop index of that kitab

class BaseSearchEngine:
    def __init__(self, th, multithreading = False):
        self.th = th
        self.multithreading = multithreading

    def getIndexedVersion(self, name):
        """
        return a Version-Release string if in index, otherwise return None
        """
        raise NotImplementedError

    def queryIndex(self, queryString):
        """
        return an interatable of fields dict
        this method must be overridden in implementation specific way
        """
        raise NotImplementedError

    def indexingStart(self):
        """
        should be called before any sequence of indexing Ops, reindexAll() calls this method automatically
        """
        pass

    def indexingEnd(self):
        """
        should be called after a sequence of indexing Ops, reindexAll() calls this method automatically
        """
        pass

    def reload(self):
        """
        called after commiting changes to index (eg. adding or dropping from index)
        """
        pass

    def dropKitabIndex(self, name):
        """
        drop search index for a given Kitab name
        you need to call indexingStart() before this and indexingEnd() after it
        this method must be overridden in implementation specific way
        """
        raise NotImplementedError

    def addDocumentToIndex(self, name, vrr, nodeIdNum, title, content, tags):
        """
        this method must be overridden in implementation specific way
        """
        raise NotImplementedError

    def dropAll(self):
        raise NotImplementedError
        # NOTE: the following implementation is buggy, since there could be documents index but no longer exists
        #t = []
        #self.indexingStart()
        #for i in self.th.getManagedUriList(): self.dropKitabIndex(i)
        #self.indexingEnd()

    def dropChanged(self):
        """
        drop index for all indexed kutub that got changed (updated or downgraded)
        this is useful if followed by indexNew
        
        no need you need to call indexingStart() indexingEnd() around this
        """
        self.indexingStart()
        m = self.th.getMeta()
        for n in self.th.getKitabList():
            vr = self.getIndexedVersion(n)
            if vr and vr != metaVrr(m.getLatestKitab(n)):
                self.dropKitabIndex(n)
        self.indexingEnd()

    def dropOld(self):
        """
        drop index for all indexed kutub that got updated
        this is useful if followed by indexNew
        
        no need you need to call indexingStart() indexingEnd() around this
        """
        self.indexingStart()
        m = self.th.getMeta()
        for n in self.th.getKitabList():
            vr = self.getIndexedVersion(n)
            if vr and strverscmp(vr,metaVrr(m.getLatestKitab(n))) > 0:
                self.dropKitabIndex(n)
        self.indexingEnd()

    def indexNew(self):
        """
        index all non-indexed
        
        no need to call indexingStart() indexingEnd() around this
        """
        self.indexingStart()
        for n in self.th.getKitabList():
            vr = self.getIndexedVersion(n)
            if not vr:
                self.indexKitab(n)
        self.indexingEnd()

    def refresh(self):
        """
        drop changed then index them along with new unindexed.
        
        no need to call indexingStart() indexingEnd() around this
        """
        self.dropChanged()
        self.indexNew()

    def reindexAll(self):
        """
        no need to call indexingStart() indexingEnd() around this
        """
        self.dropAll()
        # FIXME: should be dropAll() then usual index not reindex
        t = []
        self.indexingStart()
        for n in self.th.getKitabList():
            self.indexKitab(n)
        # if threading is supported by indexer it would look like
        #if self.multithreading:
        #    for i in self.getManagedUriList():
        #        t.append(threading.Thread(target=self.indexKitab,args=(i,)))
        #        t[-1].start()
        #    for i in t: i.join()
        self.indexingEnd()

    def reindexKitab(self, name):
        """
        you need to call indexingStart() before this and indexingEnd() after it
        """
        self.dropKitabIndex(name)
        self.indexKitab(name)

    def __ix_nodeStart(self, node, name, vrr, iix):
        # NOTE: benchmarks says append then join is faster than s += "foo"
        tags = node.getTags()
        tag_flags = node.getTagFlags()
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
        iix.tags.extend(map(lambda t: tags[t] == None and t or u'.'.join((t,tags[t])),
                                          node.getTagsByFlagsMask(TAG_FLAGS_IX_TAG)))
    
    def __ix_nodeEnd(self, node, name, vrr, iix):
        # index extra sub fields if any
        if iix.sub_f_node_idnums and iix.sub_f_node_idnums[-1] == node.idNum:
            n = iix.sub_f_node_idnums.pop()
            i = iix.sub_f_content_index.pop()
            j = iix.sub_f_tags_index.pop()
            c = u"".join(iix.contents[i:])
            T = u" ".join(iix.tags[j:])
            del iix.tags[j:]
            k = iix.main_f_content_index[-1] # the nearest header title index
            N = iix.main_f_node_idnums[-1] # the nearest header node.idNum
            # NOTE: the above two lines means that a sub ix fields should be children of some main field (header)
            t = iix.contents[k]
            self.addDocumentToIndex(unicode(name), vrr, N, t, c, T)
        # index consuming main indexing fields if any
        if iix.main_f_node_idnums and iix.main_f_node_idnums[-1] == node.idNum: 
            n = iix.main_f_node_idnums.pop()
            i = iix.main_f_content_index.pop()
            j = iix.main_f_tags_index.pop()
            t = iix.contents[i]
            c = (u"".join(iix.contents[i:])).strip()
            del iix.contents[i:]
            T = u" ".join(iix.tags[j:])
            del iix.tags[j:]
            self.addDocumentToIndex(unicode(name), vrr, n, t.strip(), c, T)

    class __IIX(object):
        "internal indexing object"
        def __init__(self):
            # independent arrays
            self.contents = [] # array of contents to be indexed
            self.tags = [] # array of ix tags
            # main_f* parallel arrays
            self.main_f_node_idnums = [] # array of node.idNum of consuming ix fields (ie. header)
            self.main_f_content_index = [] # array of the starting index in self.contents for each main ix field (ie. header)
            self.main_f_tags_index = [] # array of the starting index in self.contents for each main ix field (ie. header)
            # sub_f* parallel arrays
            self.sub_f_node_idnums = [] # array of node.idNum for each sub ix field
            self.sub_f_content_index = [] # array of the starting index in self.contents for each sub ix field
            self.sub_f_tags_index = [] # array of the starting index in self.tags for each sub ix field
            # TODO: benchmark which is faster parallel arrays or small tubles sub_field = (idNum,content_i,tag_i)

    def indexKitab(self, name):
        """
        create search index for a given Kitab name
        NOTE: you need to call indexingStart() before this and indexingEnd() after it
        """
        #print "creating index for kitab with name:", name
        ki = self.th.getKitab(name)
        self.th.getMeta().setIndexedFlags(ki.uri, 1)
        vrr = metaVrr(ki.meta)
        iix = self.__IIX()
        ki.root.traverser(3,
                          self.__ix_nodeStart,
                          self.__ix_nodeEnd,
                          name,
                          vrr,
                          iix)
        self.th.getMeta().setIndexedFlags(ki.uri, 2)

