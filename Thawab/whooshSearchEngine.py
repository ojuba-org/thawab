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

from whoosh import query
from whoosh.index import EmptyIndexError, create_in, open_dir
from whoosh.highlight import highlight, SentenceFragmenter, BasicFragmentScorer, FIRST, HtmlFormatter
from whoosh.filedb.filestore import FileStorage
from whoosh.fields import Schema, ID, IDLIST, TEXT
from whoosh.formats import Frequency

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

from whoosh.qparser import MultifieldParser, FieldAliasPlugin, QueryParserError, BoostPlugin, GroupPlugin, PhrasePlugin, RangePlugin, SingleQuotesPlugin, Group, AndGroup, OrGroup, AndNotGroup, AndMaybeGroup, Singleton, BasicSyntax, Plugin, White, Token

from whoosh.qparser import CompoundsPlugin, NotPlugin, WildcardPlugin

class ThCompoundsPlugin(Plugin):
    """Adds the ability to use &, |, &~, and &! to specify
    query constraints.
    
    This plugin is included in the default parser configuration.
    """
    
    def tokens(self):
        return ((ThCompoundsPlugin.AndNot, -10), (ThCompoundsPlugin.AndMaybe, 0), (ThCompoundsPlugin.And, 0),
                (ThCompoundsPlugin.Or, 0))
    
    def filters(self):
        return ((ThCompoundsPlugin.do_compounds, 600), )

    @staticmethod
    def do_compounds(parser, stream):
        newstream = stream.empty()
        i = 0
        while i < len(stream):
            t = stream[i]
            ismiddle = newstream and i < len(stream) - 1
            if isinstance(t, Group):
                newstream.append(ThCompoundsPlugin.do_compounds(parser, t))
            elif isinstance(t, (ThCompoundsPlugin.And, ThCompoundsPlugin.Or)):
                if isinstance(t, ThCompoundsPlugin.And):
                    cls = AndGroup
                else:
                    cls = OrGroup
                
                if cls != type(newstream) and ismiddle:
                    last = newstream.pop()
                    rest = ThCompoundsPlugin.do_compounds(parser, cls(stream[i+1:]))
                    newstream.append(cls([last, rest]))
                    break
            
            elif isinstance(t, ThCompoundsPlugin.AndNot):
                if ismiddle:
                    last = newstream.pop()
                    i += 1
                    next = stream[i]
                    if isinstance(next, Group):
                        next = ThCompoundsPlugin.do_compounds(parser, next)
                    newstream.append(AndNotGroup([last, next]))
            
            elif isinstance(t, ThCompoundsPlugin.AndMaybe):
                if ismiddle:
                    last = newstream.pop()
                    i += 1
                    next = stream[i]
                    if isinstance(next, Group):
                        next = ThCompoundsPlugin.do_compounds(parser, next)
                    newstream.append(AndMaybeGroup([last, next]))
            else:
                newstream.append(t)
            i += 1
        
        return newstream
    
    class And(Singleton):
        expr = re.compile(u"&")
        
    class Or(Singleton):
        expr = re.compile(u"\|")
        
    class AndNot(Singleton):
        expr = re.compile(u"&!")
        
    class AndMaybe(Singleton):
        expr = re.compile(u"&~") # when using Arabic keyboard ~ is shift+Z

class ThFieldsPlugin(Plugin):
    """Adds the ability to specify the field of a clause using a colon.
    
    This plugin is included in the default parser configuration.
    """
    
    def tokens(self):
        return ((ThFieldsPlugin.Field, 0), )
    
    def filters(self):
        return ((ThFieldsPlugin.do_fieldnames, 100), )

    @staticmethod
    def do_fieldnames(parser, stream):
        newstream = stream.empty()
        newname = None
        for i, t in enumerate(stream):
            if isinstance(t, ThFieldsPlugin.Field):
                valid = False
                if i < len(stream) - 1:
                    next = stream[i+1]
                    if not isinstance(next, (White, ThFieldsPlugin.Field)):
                        newname = t.fieldname
                        valid = True
                if not valid:
                    newstream.append(Word(t.fieldname, fieldname=parser.fieldname))
                continue
            
            if isinstance(t, Group):
                t = ThFieldsPlugin.do_fieldnames(parser, t)
            newstream.append(t.set_fieldname(newname))
            newname = None
        
        return newstream
    
    class Field(Token):
        expr = re.compile(u"(\w[\w\d]*):", re.U)
        
        def __init__(self, fieldname):
            self.fieldname = fieldname
        
        def __repr__(self):
            return "<%s:>" % self.fieldname
        
        def set_fieldname(self, fieldname):
            return self.__class__(fieldname)
        
        @classmethod
        def create(cls, parser, match):
            return cls(match.group(1))

class ThNotPlugin(Plugin):
    """Adds the ability to negate a clause by preceding it with !.
    
    This plugin is included in the default parser configuration.
    """
    
    def tokens(self):
        return ((ThNotPlugin.Not, 0), )
    
    def filters(self):
        return ((ThNotPlugin.do_not, 800), )
    
    @staticmethod
    def do_not(parser, stream):
        newstream = stream.empty()
        notnext = False
        for t in stream:
            if isinstance(t, ThNotPlugin.Not):
                notnext = True
                continue
            
            if notnext:
                t = NotGroup([t])
            newstream.append(t)
            notnext = False
            
        return newstream
    
    class Not(Singleton):
        expr = re.compile(u"!")

class ThWildcardPlugin(Plugin):
    """Adds the ability to specify wildcard queries by using asterisk and
    question mark characters in terms. Note that these types can be very
    performance and memory intensive. You may consider not including this
    type of query.
    
    This plugin is included in the default parser configuration.
    """
    
    def tokens(self):
        return ((ThWildcardPlugin.Wild, 0), )
    
    class Wild(BasicSyntax):
        expr = re.compile(u"[^ \t\r\n*?]*(\\*|\\?|؟)\\S*")
        qclass = query.Wildcard
        
        def __repr__(self):
            r = "%s:wild(%r)" % (self.fieldname, self.text)
            if self.boost != 1.0:
                r += "^%s" % self.boost
            return r
        
        @classmethod
        def create(cls, parser, match):
            return cls(match.group(0).replace(u'؟',u'?'))

def ThMultifieldParser(schema=None):
  plugins = (BoostPlugin, ThCompoundsPlugin, ThFieldsPlugin, GroupPlugin,
      ThNotPlugin, PhrasePlugin, RangePlugin, SingleQuotesPlugin,
      ThWildcardPlugin, FieldAliasPlugin({
        u"kitab":(u"كتاب",),
        u"title":(u"عنوان",),
        u"tags":(u"وسوم",)})
      )
  p = MultifieldParser(("title","content",), schema=schema, plugins=plugins)
  # to add a plugin use: p.add_plugin(XYZ)
  return p

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
        #content=TEXT(stored=False,analyzer=analyzer, vector=Frequency(analyzer=analyzer)), # with term vector
        tags=IDLIST(stored=False)
      )
      self.indexer=create_in(ix_dir,schema)
    #self.__ix_qparser = ThMultifieldParser(self.th, ("title","content",), schema=self.indexer.schema)
    self.__ix_qparser = ThMultifieldParser(self.indexer.schema)
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
    except QueryParserError: return None
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
    self.__ix_writer.commit(optimize=True)
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
    ki=self.th.getKitab(name)
    if ki: self.th.getMeta().setIndexedFlags(ki.uri, 1)
    print "dropping index for kitab name:", name,
    w, c = self.__ix_writer, False
    if not w: w, c=self.indexer.writer(), True # creates a writer internally if one is not defined
    # NOTE: because the searcher could be limited do a loop that keeps deleting till the query is empty
    while(w.delete_by_term('kitab', name)):
      print "*",
    print
    if c: w.commit()
    if ki: self.th.getMeta().setIndexedFlags(ki.uri, 0)

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
    # NOTE: this method is overridden here because we need to commit between dropping and creating a new index.
    # NOTE: can't use updateDocument because each Kitab contains many documents
    self.dropKitabIndex(name); self.__ix_writer.commit(); self.indexKitab(name)

  def addDocumentToIndex(self, name, vrr, nodeIdNum, title, content, tags):
    """
    this method must be overridden in implementation specific way
    """
    if content: self.__ix_writer.add_document(kitab=name, vrr=vrr, nodeIdNum=unicode(nodeIdNum), title=title, content=content, tags=tags)

  def keyterms(self, kitab, vrr, nodeIdNum):
    s = self.indexer.searcher()
    dn = s.document_number(kitab=kitab, vrr=vrr, nodeIdNum=unicode(nodeIdNum))
    if dn == None: return None,[]
    print " ## ", dn
    r=s.key_terms([dn], "content", numterms=5)
    return dn,r

  def related(self, kitab, vrr, nodeIdNum):
    dn,kt=self.keyterms(kitab, vrr, nodeIdNum)
    if not dn: return None
    for t,r in kt:
      print "term=", t, " @ rank=",r
    q = query.Or([query.Term("content", t) for (t,r) in kt])
    results = self.indexer.searcher().search(q, limit=10)
    for i, fields in enumerate(results):
      if results.docnum(i) != dn:
        print fields['kitab'],"\t\t",str(fields['nodeIdNum']),"\t\t",fields['title']

