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
try:
  from pyparsing import ParseBaseException, printables, alphanums, ZeroOrMore, OneOrMore, Group, Combine, Suppress, Optional, FollowedBy, Literal, CharsNotIn, Word, Keyword, Regex, Empty, White, Forward, QuotedString, StringEnd, ParserElement
except ImportError:
  from whoosh.support.pyparsing import ParseBaseException, printables, alphanums, ZeroOrMore, OneOrMore, Group, Combine, Suppress, Optional, FollowedBy, Literal, CharsNotIn, Word, Keyword, Regex, Empty, White, Forward, QuotedString, StringEnd, ParserElement

def make_thawab_qparser():
    escapechar = "\\"
    
    #wordchars = printables
    #for specialchar in '*?^():"{}[] ' + escapechar:
    #    wordchars = wordchars.replace(specialchar, "")
    #wordtext = Word(wordchars)
    
    wordtext = CharsNotIn(u'\\*؟?^():"{}[]!&| ')
    escape = Suppress(escapechar) + (Word(printables, exact=1) | White(exact=1))
    wordtoken = Combine(OneOrMore(wordtext | escape))
    
    # A plain old word.
    plainWord = Group(wordtoken).setResultsName("Word")
    
    # A wildcard word containing * or ?.
    wildchars = Word(u"؟?*")
    # Start with word chars and then have wild chars mixed in
    wildmixed = wordtoken + OneOrMore(wildchars + Optional(wordtoken))
    # Or, start with wildchars, and then either a mixture of word and wild chars, or the next token
    wildstart = wildchars + (OneOrMore(wordtoken + Optional(wildchars)) | FollowedBy(White() | StringEnd()))
    wildcard = Group(Combine(wildmixed | wildstart)).setResultsName("Wildcard")
    
    # A range of terms
    startfence = Literal("[") | Literal("{")
    endfence = Literal("]") | Literal("}")
    rangeitem = QuotedString('"') | wordtoken
    openstartrange = Group(Empty()) + Suppress(Keyword("TO") + White()) + Group(rangeitem)
    openendrange = Group(rangeitem) + Suppress(White() + Keyword("TO")) + Group(Empty())
    normalrange = Group(rangeitem) + Suppress(White() + Keyword("TO") + White()) + Group(rangeitem)
    range = Group(startfence + (normalrange | openstartrange | openendrange) + endfence).setResultsName("Range")

#    rangeitem = QuotedString('"') | wordtoken
#    rangestartitem = Group((rangeitem + Suppress(White())) | Empty()).setResultsName("rangestart")
#    rangeenditem = Group((Suppress(White()) + rangeitem) | Empty()).setResultsName("rangeend")
#    rangestart = (Literal("{") | Literal("[")) + rangestartitem
#    rangeend = rangeenditem + (Literal("}") | Literal("]"))
#    range =  Group(rangestart + Suppress(Literal("TO")) + rangeend).setResultsName("Range")
    
    # A word-like thing
    generalWord = range | wildcard | plainWord
    
    # A quoted phrase
    quotedPhrase = Group(QuotedString('"')).setResultsName("Quotes")
    
    expression = Forward()
    
    # Parentheses can enclose (group) any expression
    parenthetical = Group((Suppress("(") + expression + Suppress(")"))).setResultsName("Group")

    boostableUnit = generalWord | quotedPhrase
    boostedUnit = Group(boostableUnit + Suppress("^") + Word("0123456789", ".0123456789")).setResultsName("Boost")

    # The user can flag that a parenthetical group, quoted phrase, or word
    # should be searched in a particular field by prepending 'fn:', where fn is
    # the name of the field.
    fieldableUnit = parenthetical | boostedUnit | boostableUnit
    # fieldedUnit = Group(Word(alphanums + "_"+u'\u0643\u062a\u0627\u0628') + Suppress(':') + fieldableUnit).setResultsName("Field") # replace u'\u0643\u062a\u0627\u0628' with Arabic letters
    fieldedUnit = Group(Regex(u'\w+', re.U) + Suppress(':') + fieldableUnit).setResultsName("Field")
    # Units of content
    unit = fieldedUnit | fieldableUnit

    # TODO: add translation support for NOT and for ANDNOT
    # A unit may be "not"-ed.
    operatorNot = Group(Suppress('!') +  Suppress(ZeroOrMore(White())) + unit).setResultsName("Not")
    generalUnit = operatorNot | unit

    andToken = Literal('&')
    orToken = Literal("|")
    andNotToken = Literal("&!")
    
    operatorAnd = Group(generalUnit +  Suppress(ZeroOrMore(White())) + Suppress(andToken) +  Suppress(ZeroOrMore(White())) + expression).setResultsName("And")
    operatorOr = Group(generalUnit +  Suppress(ZeroOrMore(White())) + Suppress(orToken) +  Suppress(ZeroOrMore(White())) + expression).setResultsName("Or")
    operatorAndNot = Group(unit + Suppress(ZeroOrMore(White())) + Suppress(andNotToken) + Suppress(ZeroOrMore(White())) + unit).setResultsName("AndNot")

    expression << (OneOrMore(operatorAnd | operatorOr | operatorAndNot | generalUnit | Suppress(White())) | Empty())
    
    toplevel = Group(expression).setResultsName("Toplevel") + StringEnd()
    
    return toplevel.parseString

