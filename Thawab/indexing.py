# -*- coding: utf-8 -*-
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
import re
#harakat="ًٌٍَُِّْـ".decode('utf-8')
#normalize_tb=dict(map(lambda i: (ord(i),None),list(harakat)))
#normalize_tb[ord('ة'.decode('utf-8'))]=ord('ه'.decode('utf-8'))
#for i in list("ىئإؤأآء".decode('utf-8')):
#  normalize_tb[ord(i)]=ord('ا'.decode('utf-8'))

normalize_tb={
65: 97, 66: 98, 67: 99, 68: 100, 69: 101, 70: 102, 71: 103, 72: 104, 73: 105, 74: 106, 75: 107, 76: 108, 77: 109, 78: 110, 79: 111, 80: 112, 81: 113, 82: 114, 83: 115, 84: 116, 85: 117, 86: 118, 87: 119, 88: 120, 89: 121, 90: 122,
1600: None, 1569: 1575, 1570: 1575, 1571: 1575, 1572: 1575, 1573: 1575, 1574: 1575,
1577: 1607, # teh marboota ->  haa
1611: None, 1612: None, 1613: None, 1614: None, 1615: None, 1616: None, 1617: None, 1618: None, 1609: 1575}

rm_prefix=re.compile(u"^(?:ا?[وف]?((?:[بك]?ال|لل?)|[اينت])?)")
# TODO: reconsider the suffex re
rm_suffix=re.compile(u"(?:ا[نت]|[يهة]|ها|ي[هنة]|ون)$")

#rm_prefix=u"^(?:ا?[وف]?((?:[بك]?ال|لل?)|[اينت])?)"
#rm_suffix=u"(?:ا[نت]|[يهة]|ها|ي[هنة]|ون)$"
#stem_re=rm_prefix+"(\w{3,}?)"+rm_suffix
# أواستقدمتموني
# استفهام عطف جر وتعريف  (مثال: "أفككتابي تؤلف ؟" "وللآخرة فلنعد العدة"  "فالاستغفار")  أو مضارعة
# الجر والتعريف لا تجتمع مع المضارعة
prefix_re=u''.join( ( 
  u"^\u0627?" ,                # optional hamza
  u"[\u0648\u0641]?",          # optional Atf (with Waw or Faa)
  u"(?:" ,                     # nouns specific prefixes (Jar and definite article)
    u"[\u0628\u0643]?\u0627\u0644?|" ,   # optional Jar (with ba or kaf) with optional AL
    u"\u0644\u0644|" ,                   # optional LL (Jar with Lam and article )
    u"\u0644" ,                          # optional LL (Jar with Lam and article)
  u")?" ,                      # end nouns specific prefixes
  u"(\\w{2,})$" ) )            # the stem is grouped

# [اتني]|نا|ان|تا|ون|ين|تما
verb_some_subject_re=u"[\u0627\u062a\u0646\u064a]|\u0646\u0627|\u0627\u0646|\u062a\u0627|\u0648\u0646|\u064a\u0646|\u062a\u0645\u0627"
# [هن]|ني|نا|ها|هما|هم|هن|كما|كم|كن
verb_object_re=u"(?[\u0647\u0646]|\u0646\u064a|\u0646\u0627|\u0647\u0627|\u0647\u0645\u0627|\u0647\u0645|\u0647\u0646|\u0643\u0645\u0627|\u0643\u0645|\u0643\u0646)"

verb_suffix_re=u''.join( [ 
  u"(?:(?:\u0648\u0627|\u062a\u0645)|" ,           # وا|تم
  u"(?:",
    u"(?:",
    verb_some_subject_re,
    u'|\u0648|\u062a\u0645\u0648',              # و|تمو
    u")",
    verb_object_re,u'{1,2}'
  u")|(?:",
    verb_some_subject_re,
  u"))?$"])


def removeArabicSuffix(word):
  if len(word)>4:
    w=rm_suffix.sub("",word,1)
    if len(w)>2: return w
  return word

def removeArabicPrefix(word):
  if len(word)>3:
    w=rm_prefix.sub("",word,1)
    if len(w)>2: return w
  return word

def stemArabic(word):
  return removeArabicPrefix(removeArabicSuffix(unicode(word).translate(normalize_tb)))

from whoosh.lang.porter import stem
class StemFilter(object):
  """Stems (removes suffixes from) the text of tokens using the Porter stemming
  algorithm. Stemming attempts to reduce multiple forms of the same root word
  (for example, "rendering", "renders", "rendered", etc.) to a single word in
  the index.
  
  Note that I recommend you use a strategy of morphologically expanding the
  query terms (see query.Variations) rather than stemming the indexed words.
  """
  
  def __init__(self, ignore = None):
    """
    :ignore: a set/list of words that should not be stemmed. This
      is converted into a frozenset. If you omit this argument, all tokens
      are stemmed.
    """
    
    self.cache = {}
    if ignore is None:
      self.ignores = frozenset()
    else:
      self.ignores = frozenset(ignore)
  
  def clear(self):
    """
    This filter memoizes previously stemmed words to greatly speed up
    stemming. This method clears the cache of previously stemmed words.
    """
    self.cache.clear()
  
  def __call__(self, tokens):
    cache = self.cache
    ignores = self.ignores
    
    for t in tokens:
      if t.stopped:
        yield t
        continue
      
      text = t.text
      if text in ignores:
        yield t
      elif text in cache:
        t.text = cache[text]
        yield t
      else:
        t.text = s = stemArabic(stem(text))
        cache[text] = s
        yield t

from whoosh.fields import Existance, KeywordAnalyzer, FieldType
class TAGSLIST(FieldType):
    """
    Configured field type for fields containing space-separated or comma-separated
    keyword-like data (such as tags). The default is to not store positional information
    (so phrase searching is not allowed in this field) and to not make the field scorable.
    
    unlike KEYWORD field type, TAGS list does not count frequency just existence.
    """
    
    def __init__(self, stored = False, lowercase = False, commas = False,
                 scorable = False, unique = False, field_boost = 1.0):
        """
        :stored: Whether to store the value of the field with the document.
        :comma: Whether this is a comma-separated field. If this is False
            (the default), it is treated as a space-separated field.
        :scorable: Whether this field is scorable.
        """
        
        ana = KeywordAnalyzer(lowercase = lowercase, commas = commas)
        self.format = Existance(analyzer = ana, field_boost = field_boost)
        self.scorable = scorable
        self.stored = stored
        self.unique = unique

