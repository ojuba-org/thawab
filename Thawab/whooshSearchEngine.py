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
from tags import *
from meta import prettyId,makeId

from whoosh.index import EmptyIndexError, create_in, open_dir
from whoosh.highlight import highlight, SentenceFragmenter, BasicFragmentScorer, FIRST, HtmlFormatter
from whoosh.filedb.filestore import FileStorage
from whoosh.fields import Schema, ID, IDLIST, TEXT

from whoosh.lang.porter import stem
from whoosh.analysis import StandardAnalyzer, StemFilter

from stemming import stemArabic

def stemfn(word): return stemArabic(stem(word))
# word_re=ur"[\w\u064e\u064b\u064f\u064c\u0650\u064d\u0652\u0651\u0640]"
analyzer=StandardAnalyzer(expression=ur"[\w\u064e\u064b\u064f\u064c\u0650\u064d\u0652\u0651\u0640]+(?:\.?[\w\u064e\u064b\u064f\u064c\u0650\u064d\u0652\u0651\u0640]+)*") | StemFilter(stemfn)

#from whoosh.fields import FieldType, KeywordAnalyzer
#try: from whoosh.fields import Existence
#except ImportError: from whoosh.fields import Existance as Existence

#class TAGSLIST(FieldType):
#    """
#    Configured field type for fields containing space-separated or comma-separated
#    keyword-like data (such as tags). The default is to not store positional information
#    (so phrase searching is not allowed in this field) and to not make the field scorable.
#    
#    unlike KEYWORD field type, TAGS list does not count frequency just existence.
#    """
#    
#    def __init__(self, stored = False, lowercase = False, commas = False,
#                 scorable = False, unique = False, field_boost = 1.0):
#        """
#        :stored: Whether to store the value of the field with the document.
#        :comma: Whether this is a comma-separated field. If this is False
#            (the default), it is treated as a space-separated field.
#        :scorable: Whether this field is scorable.
#        """
#        
#        ana = KeywordAnalyzer(lowercase = lowercase, commas = commas)
#        self.format = Existence(analyzer = ana, field_boost = field_boost)
#        self.scorable = scorable
#        self.stored = stored
#        self.unique = unique

from whoosh.qparser import MultifieldParser
from whooshQParser import make_thawab_qparser, ParseBaseException

TH_Q_PARSER=make_thawab_qparser()

class ThMultifieldParser(MultifieldParser):
  """
  Thawab specific MultifieldParser
  """
  _fieldsTranslation={
    u"كتاب":u"kitab", u"عنوان":u"title", u"وسوم":u"tags",
  }
  def __init__(self, th, *args, **kw):
    self.th=th
    MultifieldParser.__init__(self, *args, **kw)
    self.parser=TH_Q_PARSER

  def _trField(self, fieldname, text):
    f=self._fieldsTranslation.get(fieldname,None)
    if f: fieldname=f
    if fieldname=="kitab":
      text=makeId(text)
    return fieldname, text

  def _Wildcard(self, node, fieldname):
    return self.make_wildcard(fieldname, node[0].replace(u'؟',u'?'))


  def make_term(self, fieldname, text):
    fieldname, text=self._trField(fieldname, text)
    return MultifieldParser.make_term(self, fieldname, text)

  def make_phrase(self, fieldname, text):
    fieldname, text=self._trField(fieldname, text)
    return MultifieldParser.make_phrase(self, fieldname, text)

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
            if t.matched: ttxt = "\0"+ttxt.upper()+"\010"
            output.append(ttxt)
            index = t.endchar
        
        output.append(text[index:fragment.endchar])
        return "".join(output)

    def __call__(self, text, fragments):
        return self.between.join((self._format_fragment(text, fragment)
                                  for fragment in fragments))


from baseSearchEngine import BaseSearchEngine
class SearchEngine(BaseSearchEngine):
  def __init__(self, th):
    BaseSearchEngine.__init__(self, th, False)
    self.__ix_writer = None
    ix_dir=os.path.join(th.prefixes[0],'index')
    # try to load a pre-existing index
    try: self.indexer=open_dir(ix_dir)
    except EmptyIndexError:
      # create a new one
      schema = Schema(
        kitab=ID(stored=True),
        vrr=ID(stored=True,unique=False), # version release
        nodeIdNum=ID(stored=True,unique=False), 
        title=TEXT(stored=True,field_boost=1.5, analyzer=analyzer),
        content=TEXT(stored=False,analyzer=analyzer),
        tags=IDLIST(stored=False)
      )
      self.indexer=create_in(ix_dir,schema)
    self.__ix_qparser = ThMultifieldParser(self.th, ("title","content",), schema=self.indexer.schema)
    #self.__ix_pre=whoosh.query.Prefix
    self.__ix_searcher= self.indexer.searcher()

  def __del__(self):
    if self.__ix_writer: self.__ix_writer.commit()

  def getIndexedVersion(self, name):
    """
    return a Version-Release string if in index, otherwise return None
    """
    d=self.__ix_searcher.document(kitab=unicode(makeId(name)))
    if d: return d['vrr']
    return None

  def queryIndex(self, queryString):
    """return an interatable of fields dict"""
    # FIXME: the return should not be implementation specific
    try: r=self.__ix_searcher.search(self.__ix_qparser.parse(queryString), limit=500)
    except ParseBaseException: return None
    return r

  def resultExcerpt(self, results, i, ki=None):
    # FIXME: this should not be implementation specific
    if not ki:
      r=results[i]
      name=r['kitab']
      v=r['vrr'].split('-')[0]
      m=self.th.getMeta().getLatestKitabV(name,v)
      ki=self.th.getCachedKitab(m['uri'])
    num=int(results[i]['nodeIdNum'])
    node=ki.getNodeByIdNum(num)
    n=ki.toc.next(node)
    if n: ub=n.globalOrder
    else: ub=-1
    txt=node.toText(ub)
    s=set()
    #results.query.all_terms(s) # return (field,term) pairs 
    results.query.existing_terms(self.indexer.reader(), s, phrases=True) # return (field,term) pairs  # self.self.__ix_searcher.reader()
    terms=dict(
      map(lambda i: (i[1],i[0]),
      filter(lambda j: j[0]=='content' or j[0]=='title', s))).keys()
    #print "txt=[%s]" % len(txt)
    snippet=txt[:min(len(txt),512)] # dummy summary
    snippet=highlight(txt, terms, analyzer,
      SentenceFragmenter(sentencechars = ".!?؟\n"), HtmlFormatter(between=u"\u2026\n"),
      top=3, scorer=BasicFragmentScorer, minscore=1, order=FIRST)
    #snippet=highlight(txt, terms, analyzer,
    #   SentenceFragmenter(sentencechars = ".!?"), ExcerptFormatter(between = u"\u2026\n"), top=3,
    #   scorer=BasicFragmentScorer, minscore=1,
    #   order=FIRST)
    return snippet

  def indexingStart(self):
    """
    should be called before any sequence of indexing Ops, reindexAll() calls this method automatically
    """
    if not self.__ix_writer: self.__ix_writer=self.indexer.writer()

  def indexingEnd(self):
    """
    should be called after a sequence of indexing Ops, reindexAll() calls this method automatically
    """
    self.__ix_writer.commit()
    self.indexer.optimize()
    self.reload()

  def reload(self):
    """
    called after commiting changes to index (eg. adding or dropping from index)
    """
    self.indexer=self.indexer.refresh()
    self.__ix_searcher= self.indexer.searcher()
    self.__ix_writer = None

  def dropKitabIndex(self, name):
    """
    drop search index for a given Kitab by its uri
    you need to call indexingStart() before this and indexingEnd() after it
    """
    # FIXME: it seems that this does not work correctly without commit() just after drop, this mean that reindex needs a commit in-between
    # NOTE: because the searcher could be limited do a loop that keeps deleting till the query is empty
    ki=self.th.getKitab(name)
    if ki: self.th.getMeta().setIndexedFlags(ki.uri, 1)
    print "dropping index for kitab name:", name,
    #self.indexingStart()
    while(self.indexer.delete_by_term('kitab', name)):
      print "*",
    #self.__ix_writer.commit() # without this reindexKitab won't work
    print
    if ki: self.th.getMeta().setIndexedFlags(ki.uri, 0)

  def dropAll(self):
    # FIXME: it would be more effeciant to delete the directory
    # NOTE: see http://groups.google.com/group/whoosh/browse_thread/thread/35b1700b4e4a3d5d
    self.th.getMeta().setAllIndexedFlags(1)
    self.indexingStart()
    reader = self.indexer.reader() # also self.__ix_searcher.reader()
    for docnum in reader.all_stored_fields():
      self.indexer.delete_document(docnum)
    self.indexingEnd()
    self.th.getMeta().setAllIndexedFlags(0)

  def reindexKitab(self,name):
    """
    you need to call indexingStart() before this and indexingEnd() after it
    """
    # NOTE: this method is overridden here because we need to commit between dropping and creating a new index.
    # NOTE: can't use updateDocument because each Kitab contains many documents
    self.dropKitabIndex(name); self.__ix_writer.commit(); self.indexKitab(name)

  def addDocumentToIndex(self, name, vrr, nodeIdNum, title, content, tags):
    """
    this method must be overridden in implementation specific way
    """
    if content: self.__ix_writer.add_document(kitab=name, vrr=vrr, nodeIdNum=unicode(nodeIdNum), title=title, content=content, tags=tags)


