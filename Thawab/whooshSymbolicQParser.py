# -*- coding: UTF-8 -*-
"""

Copyright © 2010, Muayyad Alsadi <alsadi@ojuba.org>

"""

import sys, os, os.path, re

from whoosh import query
from whoosh.qparser import *

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

def MultifieldSQParser(fieldnames, schema=None, fieldboosts=None, **kwargs):
  p = MultifieldParser(fieldnames, schema, fieldboosts, **kwargs)
  cp = OperatorsPlugin(And=r"&", Or=r"\|", AndNot=r"&!", AndMaybe=r"&~", Not=r'!')
  p.replace_plugin(cp)
  # FIXME: try to upsteam SFieldsPlugin
  p.remove_plugin_class(FieldsPlugin)
  p.add_plugin(SFieldsPlugin)
  return p

