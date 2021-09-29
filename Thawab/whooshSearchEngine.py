# -*- coding: UTF-8 -*-
"""

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
import sys, os, os.path, re
import shutil
from .tags import *
from .meta import prettyId,makeId

from whoosh import query
from whoosh.index import EmptyIndexError, create_in, open_dir, IndexVersionError
from whoosh.highlight import highlight, SentenceFragmenter, BasicFragmentScorer, FIRST, HtmlFormatter
from whoosh.filedb.filestore import FileStorage
from whoosh.fields import Schema, ID, IDLIST, TEXT
from whoosh.formats import Frequency
from whoosh.qparser import QueryParserError
from whoosh.lang.porter import stem
from whoosh.analysis import StandardAnalyzer, StemFilter

try:
    from whoosh.index import _CURRENT_TOC_VERSION as whoosh_ix_ver
except ImportError:
    from whoosh.filedb.fileindex import _INDEX_VERSION as whoosh_ix_ver

from .stemming import stemArabic

def stemfn(word): return stemArabic(stem(word))
# word_re = ur"[\w\u064e\u064b\u064f\u064c\u0650\u064d\u0652\u0651\u0640]"
analyzer = StandardAnalyzer(expression = r"[\w\u064e\u064b\u064f\u064c\u0650\u064d\u0652\u0651\u0640]+(?:\.?[\w\u064e\u064b\u064f\u064c\u0650\u064d\u0652\u0651\u0640]+)*") | StemFilter(stemfn)

from whoosh.qparser import FieldAliasPlugin
from .whooshSymbolicQParser import MultifieldSQParser

class ExcerptFormatter(object):
        def __init__(self, between = "..."):
                self.between = between
                
        def _format_fragment(self, text, fragment):
                output = []
                index = fragment.startchar
                
                for t in fragment.matches:
                        if t.startchar > index:
                                output.append(text[index:t.startchar])
                        
                        ttxt = text[t.startchar:t.endchar]
                        if t.matched:
                            ttxt = "\0" + ttxt.upper() + "\010"
                        output.append(ttxt)
                        index = t.endchar
                
                output.append(text[index:fragment.endchar])
                return "".join(output)

        def __call__(self, text, fragments):
                return self.between.join((self._format_fragment(text, fragment)
                                          for fragment in fragments))


from .baseSearchEngine import BaseSearchEngine
class SearchEngine(BaseSearchEngine):
    def __init__(self, th):
        BaseSearchEngine.__init__(self, th, False)
        self.__ix_writer = None
        ix_dir = os.path.join(th.prefixes[0],'index', "ix_" + str(whoosh_ix_ver))
        if not os.path.isdir(ix_dir):
            os.makedirs(ix_dir)
        # try to load a pre-existing index
        try:
            self.indexer = open_dir(ix_dir)
        except (EmptyIndexError, IndexVersionError):
            # create a new one
            try:
                shutil.rmtree(ix_dir, True)
                os.makedirs(ix_dir)
            except OSError:
                pass
            schema = Schema(
                kitab = ID(stored = True),
                vrr = ID(stored = True, unique = False), # version release
                nodeIdNum = ID(stored = True, unique = False), 
                title = TEXT(stored = True, field_boost = 1.5, analyzer = analyzer),
                content = TEXT(stored = False,analyzer = analyzer),
                #content = TEXT(stored = False,analyzer = analyzer,
                #vector = Frequency(analyzer = analyzer)), # with term vector
                tags=IDLIST(stored = False)
            )
            self.indexer = create_in(ix_dir, schema)
        #self.__ix_qparser = ThMultifieldParser(self.th, ("title","content",), schema=self.indexer.schema)
        self.__ix_qparser = MultifieldSQParser(("title","content",), self.indexer.schema)
        self.__ix_qparser.add_plugin(FieldAliasPlugin({
                "kitab":("كتاب",),
                "title":("عنوان",),
                "tags":("وسوم",)})
        )
        #self.__ix_pre = whoosh.query.Prefix
        self.__ix_searcher =  self.indexer.searcher()

    def __del__(self):
        if self.__ix_writer: self.__ix_writer.commit()

    def getIndexedVersion(self, name):
        """
        return a Version-Release string if in index, otherwise return None
        """
        try:
            d = self.__ix_searcher.document(kitab = str(makeId(name)))
        except TypeError:
            return None
        except KeyError:
            return None
        if d:
            return d['vrr']
        return None

    def queryIndex(self, queryString):
        """return an interatable of fields dict"""
        # FIXME: the return should not be implementation specific
        try:
            r = self.__ix_searcher.search(self.__ix_qparser.parse(queryString), limit = 500)
        except QueryParserError:
            return None
        return r

    def resultExcerpt(self, results, i, ki = None):
        # FIXME: this should not be implementation specific
        if not ki:
            r = results[i]
            name = r['kitab']
            v = r['vrr'].split('-')[0]
            m = self.th.getMeta().getLatestKitabV(name,v)
            ki = self.th.getCachedKitab(m['uri'])
        num = int(results[i]['nodeIdNum'])
        node = ki.getNodeByIdNum(num)
        n = ki.toc.next(node)
        
        if n:
            ub = n.globalOrder
        else:
            ub = -1
        txt = node.toText(ub)
        
        s = set()
        #results.query.all_terms(s) # return (field,term) pairs
        # return (field,term) pairs    # self.self.__ix_searcher.reader() 
        s = results.q.existing_terms(self.indexer.reader(), phrases = True)
        #s = set([i.decode('utf_8') for i in s])
        terms = list(dict(
                [(i[1],i[0]) for i in [j for j in s if j[0] == 'content' or j[0] == 'title']]).keys())
        #print "txt = [%s]" % len(txt)
        terms = [i.decode('utf_8') for i in terms]
        snippet_dummy = txt[:min(len(txt),512)] # dummy summary
        snippet = highlight(txt,
                            terms,
                            analyzer,
                            SentenceFragmenter(sentencechars = ".!?؟\n"),
                            HtmlFormatter(between = "\u2026\n"),
                            top = 3,
                            scorer = BasicFragmentScorer,
                            minscore = 1,
                            order = FIRST)
        #snippet = highlight(txt, terms, analyzer,
        #     SentenceFragmenter(sentencechars = ".!?"), ExcerptFormatter(between = u"\u2026\n"), top = 3,
        #     scorer = BasicFragmentScorer, minscore = 1,
        #     order = FIRST)
        #print snippet
        if len(snippet) > 1: return snippet
        else: return snippet_dummy

    def indexingStart(self):
        """
        should be called before any sequence of indexing Ops, reindexAll() calls this method automatically
        """
        if not self.__ix_writer:
            try:
                self.__ix_writer = self.indexer.writer()
            except OSError as e:
                print('*** whooshSearchEnfine.indexingStart: %s', e)
                

    def indexingEnd(self):
        """
        should be called after a sequence of indexing Ops, reindexAll() calls this method automatically
        """
        self.__ix_writer.commit(optimize = True)
        # self.indexer.optimize() # no need for this with optimize in previous line
        self.reload()

    def reload(self):
        """
        called after commiting changes to index (eg. adding or dropping from index)
        """
        self.__ix_searcher = self.__ix_searcher.refresh() # no need to obtain new one with self.indexer.searcher()
        self.__ix_writer = None

    def dropKitabIndex(self, name):
        """
        drop search index for a given Kitab by its uri
        if you call indexingStart() before this
        then you must call indexingEnd() after it
        """
        # FIXME: it seems that this used not work correctly without commit() just after drop, this mean that reindex needs a commit in-between
        ki = self.th.getKitab(name)
        if ki:
            self.th.getMeta().setIndexedFlags(ki.uri, 1)
        print("dropping index for kitab name:", name, end=' ')
        w, c = self.__ix_writer, False
        if not w:
            w, c = self.indexer.writer(), True # creates a writer internally if one is not defined
        # NOTE: because the searcher could be limited do a loop that keeps deleting till the query is empty
        while(w.delete_by_term('kitab', name)):
            print("*", end=' ')
        print()
        if c:
            w.commit()
        if ki:
            self.th.getMeta().setIndexedFlags(ki.uri, 0)

    def dropAll(self):
        # FIXME: it would be more effeciant to delete the directory
        # NOTE: see http://groups.google.com/group/whoosh/browse_thread/thread/35b1700b4e4a3d5d
        self.th.getMeta().setAllIndexedFlags(1)
        self.indexingStart()
        reader = self.indexer.reader() # also self.__ix_searcher.reader()
        for docnum in reader.all_stored_fields():
            self.__ix_writer.delete_document(docnum)
        self.indexingEnd()
        self.th.getMeta().setAllIndexedFlags(0)

    def reindexKitab(self,name):
        """
        you need to call indexingStart() before this and indexingEnd() after it
        """
        # NOTE: this method is overridden here because we need to commit 
        # between dropping and creating a new index.
        # NOTE: can't use updateDocument because each Kitab contains many documents
        self.dropKitabIndex(name)
        self.__ix_writer.commit()
        self.indexKitab(name)

    def addDocumentToIndex(self, name, vrr, nodeIdNum, title, content, tags):
        """
        this method must be overridden in implementation specific way
        """
        if not tags: tags = [' ']
        if content:
            self.__ix_writer.add_document(kitab = name,
                                          vrr = vrr,
                                          nodeIdNum = str(nodeIdNum),
                                          title = title,
                                          content = content,
                                          tags = tags)

    def keyterms(self, kitab, vrr, nodeIdNum):
        s = self.indexer.searcher()
        dn = s.document_number(kitab = kitab, vrr = vrr, nodeIdNum = str(nodeIdNum))
        if dn  ==  None:
            return None, []
        print(" ## ", dn)
        r = s.key_terms([dn], "content", numterms = 5)
        return dn, r

    def related(self, kitab, vrr, nodeIdNum):
        dn, kt = self.keyterms(kitab, vrr, nodeIdNum)
        if not dn:
            return None
        for t, r in kt:
            print("term = ", t, " @ rank = ",r)
        q = query.Or([query.Term("content", t) for (t, r) in kt])
        results = self.indexer.searcher().search(q, limit = 10)
        for i, fields in enumerate(results):
            if results.docnum(i)  !=  dn:
                print(fields['kitab'],"\t\t",str(fields['nodeIdNum']),"\t\t",fields['title'])

