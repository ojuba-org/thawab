# -*- coding: UTF-8 -*-
"""

Copyright © 2010, Muayyad Alsadi <alsadi@ojuba.org>

"""

import sys, os, os.path, re

from whoosh import query
from whoosh.qparser import *

def MultifieldSQParser(fieldnames, schema = None, fieldboosts=None, **kwargs):
    p = MultifieldParser(fieldnames, schema, fieldboosts, **kwargs)
    cp = OperatorsPlugin(And = r"&", Or = r"\|", AndNot = r"&!", AndMaybe = r"&~", Not = r'!')
    p.replace_plugin(cp)
    return p

