# -*- coding: UTF-8 -*-
"""

Copyright © 2010, Muayyad Alsadi <alsadi@ojuba.org>

"""

import sys, os, os.path, re

from whoosh import query
from whoosh.qparser import *

class SCompoundsPlugin(Plugin):
    """Adds the ability to use &, |, &~, and &! to specify
    query constraints.
    """
    
    def tokens(self, parser):
        return ((SCompoundsPlugin.AndNot, -10), (SCompoundsPlugin.AndMaybe, -5), (SCompoundsPlugin.And, 0),
                (SCompoundsPlugin.Or, 0))
    
    def filters(self, parser):
        return ((SCompoundsPlugin.do_compounds, 600), )

    @staticmethod
    def do_compounds(parser, stream):
        newstream = stream.empty()
        i = 0
        while i < len(stream):
            t = stream[i]
            ismiddle = newstream and i < len(stream) - 1
            if isinstance(t, Group):
                newstream.append(SCompoundsPlugin.do_compounds(parser, t))
            elif isinstance(t, (SCompoundsPlugin.And, SCompoundsPlugin.Or)):
                if isinstance(t, SCompoundsPlugin.And):
                    cls = AndGroup
                else:
                    cls = OrGroup
                
                if cls != type(newstream) and ismiddle:
                    last = newstream.pop()
                    rest = SCompoundsPlugin.do_compounds(parser, cls(stream[i+1:]))
                    newstream.append(cls([last, rest]))
                    break
            
            elif isinstance(t, SCompoundsPlugin.AndNot):
                if ismiddle:
                    last = newstream.pop()
                    i += 1
                    next = stream[i]
                    if isinstance(next, Group):
                        next = SCompoundsPlugin.do_compounds(parser, next)
                    newstream.append(AndNotGroup([last, next]))
            
            elif isinstance(t, SCompoundsPlugin.AndMaybe):
                if ismiddle:
                    last = newstream.pop()
                    i += 1
                    next = stream[i]
                    if isinstance(next, Group):
                        next = SCompoundsPlugin.do_compounds(parser, next)
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

class SFieldsPlugin(Plugin):
    """This plugin does not require an English field name, so that my field aliases work"""
    
    def tokens(self, parser):
        return ((SFieldsPlugin.Field, 0), )
    
    def filters(self, parser):
        return ((SFieldsPlugin.do_fieldnames, 100), )

    @staticmethod
    def do_fieldnames(parser, stream):
        newstream = stream.empty()
        newname = None
        for i, t in enumerate(stream):
            if isinstance(t, SFieldsPlugin.Field):
                valid = False
                if i < len(stream) - 1:
                    next = stream[i+1]
                    if not isinstance(next, (White, SFieldsPlugin.Field)):
                        newname = t.fieldname
                        valid = True
                if not valid:
                    newstream.append(Word(t.fieldname, fieldname=parser.fieldname))
                continue
            
            if isinstance(t, Group):
                t = SFieldsPlugin.do_fieldnames(parser, t)
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

class SNotPlugin(Plugin):
    """Adds the ability to negate a clause by preceding it with !.
    """
    
    def tokens(self, parser):
        return ((SNotPlugin.Not, 0), )
    
    def filters(self, parser):
        return ((SNotPlugin.do_not, 800), )
    
    @staticmethod
    def do_not(parser, stream):
        newstream = stream.empty()
        notnext = False
        for t in stream:
            if isinstance(t, SNotPlugin.Not):
                notnext = True
                continue
            
            if notnext:
                t = NotGroup([t])
            newstream.append(t)
            notnext = False
            
        return newstream
    
    class Not(Singleton):
        expr = re.compile(u"!")

class SWildcardPlugin(Plugin):
    """Adds the ability to specify wildcard queries by using asterisk and
    question mark characters in terms. Note that these types can be very
    performance and memory intensive. You may consider not including this
    type of query.
    """
    
    def tokens(self, parser):
        return ((SWildcardPlugin.Wild, 0), )
    
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

def MultifieldSQParser(fieldnames, schema=None, fieldboosts=None, **kwargs):
  plugins = (BoostPlugin, SCompoundsPlugin, SFieldsPlugin, GroupPlugin,
      SNotPlugin, PhrasePlugin, RangePlugin, SingleQuotesPlugin,
      SWildcardPlugin)
  p = MultifieldParser(fieldnames, schema, fieldboosts, plugins=plugins, **kwargs)
  return p

