# -*- coding: UTF-8 -*-
"""
The string constants to handle the data model
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
from tags import *
MCACHE_BASE_FIELDS=[
  'cache_hash','repo','lang','kitab','version', 'releaseMajor', 'releaseMinor', 'type',
  'author', 'year', 'originalAuthor', 'originalYear', 'originalKitab', 'originalVersion',
  'classification'
]
MCACHE_FIELDS = MCACHE_BASE_FIELDS + ['uri', 'mtime', 'flags']

SQL_MCACHE_SET='INSERT OR REPLACE INTO meta (rowid, %s) VALUES (1, %s)' % \
  (', '.join(MCACHE_BASE_FIELDS), ', '.join(map(lambda i: ":"+i,MCACHE_BASE_FIELDS)))
SQL_MCACHE_ADD='INSERT OR REPLACE INTO meta (%s) VALUES (%s)' % \
  (', '.join(MCACHE_FIELDS), ', '.join(map(lambda i: ":"+i,MCACHE_FIELDS)))
SQL_MCACHE_DROP='DELETE FROM meta WHERE uri=?'

MCACHE_BASE="""\
CREATE TABLE "meta" (
	"cache_hash" TEXT,
	"repo" TEXT,
	"lang" TEXT,
	"kitab" TEXT,
	"version" TEXT,
	"releaseMajor" INTEGER,
	"releaseMinor" INTEGER,
	"type" INTEGER,
	"author" TEXT,
	"year" INTEGER,
	"originalAuthor" TEXT,
	"originalYear" INTEGER,
	"originalKitab" TEXT,
	"originalVersion" TEXT,
	"classification" TEXT
);"""

SQL_MCACHE_DATA_MODEL = MCACHE_BASE[:MCACHE_BASE.find('\n)')]+""",\n\
	"uri" TEXT UNIQUE,
	"mtime" FLOAT,
	"flags" INTEGER DEFAULT 0
);

CREATE INDEX MetaURIIndex on meta (uri);
CREATE INDEX MetaRepoIndex on meta (repo);
CREATE INDEX MetaLangIndex on meta (lang);
CREATE INDEX MetaKitabIndex on meta (kitab);
CREATE INDEX MetaKitabTypeIndex on meta (type);
CREATE INDEX MetaKitabVersionIndex on meta (repo,kitab,version);
CREATE INDEX MetaAuthorIndex on meta (author);
CREATE INDEX MetaYearIndex on meta (year);
CREATE INDEX MetaOriginalAuthorIndex on meta (originalAuthor);
CREATE INDEX MetaOriginalYearIndex on meta (originalYear);
CREATE INDEX MetaClassificationIndex on meta (classification);
CREATE INDEX MetaFlagsIndex on meta (flags);

CREATE TABLE "directories" (
	"abspath" TEXT,
	"mtime" FLOAT
);

"""
SQL_MCACHE_GET="""SELECT rowid,* FROM meta"""
SQL_MCACHE_GET_BY_KITAB="""SELECT rowid,* FROM meta ORDER BY kitab"""
SQL_MCACHE_GET_UNINDEXED="""SELECT rowid,* FROM meta WHERE flags=0"""
SQL_MCACHE_GET_DIRTY_INDEX="""SELECT rowid,* FROM meta WHERE flags=1"""
SQL_MCACHE_GET_INDEXED="""SELECT rowid,* FROM meta WHERE flags=2"""
SQL_MCACHE_SET_INDEXED="""UPDATE OR IGNORE meta SET flags=? WHERE uri=?"""
SQL_MCACHE_SET_ALL_INDEXED="""UPDATE OR IGNORE meta SET flags=? WHERE flags>0"""

SQL_DATA_MODEL="""\
%s

CREATE TABLE "nodes" (
	"idNum" INTEGER PRIMARY KEY NOT NULL,
	"content" TEXT,
	"parent" INTEGER,
	"globalOrder" INTEGER,
	"depth" INTEGER NOT NULL
);

CREATE TABLE "tags" (
	"idNum" INTEGER PRIMARY KEY AUTOINCREMENT NOT NULL,
	"name" VARCHAR NOT NULL,
	"flags" INTEGER NOT NULL,
	"comment" VARCHAR,
	"parent" INTEGER,
	"relation" INTEGER
);

CREATE TABLE "nodesTags" (
	"tagIdNum" INTEGER NOT NULL,
	"nodeIdNum" INTEGER NOT NULL,
	"param" VARCHAR,
	PRIMARY KEY ("tagIdNum", "nodeIdNum")
);

CREATE INDEX NodesParentIndex on nodes (parent);
CREATE INDEX NodesNodesGlobalOrderIndex on nodes (globalOrder);
CREATE INDEX NodesDepthIndex on nodes (depth);

CREATE INDEX NodesTagTagIdNumIndex on nodesTags(tagIdNum);
CREATE INDEX NodesTagNodeIdNumIndex on nodesTags(nodeIdNum);
CREATE INDEX NodesTagParamIndex on nodesTags(param);
CREATE INDEX TagsName on tags (name);

""" % MCACHE_BASE
#################################################
# arguments to make the built-in tags
STD_TAGS_ARGS=( \
  # (name, comment, flags, parent, relation)
  ("header", "an anchor that marks header in TOC.",TAG_FLAGS_FLOW_BLOCK | TAG_FLAGS_HEADER),
  ("request.fix.head", "a tag that marks an error in content.", 0),
  ("request.fix.footnote", "a tag that marks an error in content footnotes.", 0),
  ("textbody", "a tag that marks a typical text.",0),
  ("quran.tafseer.ref", 'a reference to some Ayat in tafseer (in the form of "Sura-Aya-number").', 0),
  ("embed.section.ref", 'a reference to some section in a kitab to embed (in the form of "kitabName-version/section").', 0),
  # the following index-tags marks the header
  ("hadith.authenticity", "marks the authenticity of the hadith, param values are Sahih, Hasan, weak, fabricated", TAG_FLAGS_IX_TAG),
  # new index field for rawi
  ("hadith.ruwah.rawi", "marks a rawi", TAG_FLAGS_IX_FIELD),
  # the following index-tags marks the rawi field
  ("hadith.ruwah.authenticity", "marks the authenticity of the rawi, param values are thiqah, ...,kathoob", TAG_FLAGS_IX_TAG),
  ("hadith.ruwah.tabaqa", "marks the tabaqa of the rawi, param values are sahabi,tabii,...", TAG_FLAGS_IX_TAG)
)
STD_TAGS_HASH=dict(map(lambda i: (i[0],i),STD_TAGS_ARGS))
# ENUMs
WITH_NONE=0
WITH_CONTENT=1
WITH_TAGS=2
WITH_CONTENT_AND_TAGS=3
#################################################
# SQL statements for manipulating the dataModel
SQL_GET_ALL_TAGS="""SELECT name,flags,comment,parent,relation FROM tags"""
SQL_GET_NODE_CONTENT="""SELECT content from nodes WHERE idNum=? LIMIT 1"""

SQL_GET_NODE_TAGS="""SELECT tags.name,nodesTags.param FROM nodesTags LEFT OUTER JOIN tags on nodesTags.tagIdNum=tags.idNum WHERE nodesTags.nodeIdNum=?"""

# FIXME: all sql that uses SQL_NODE_ARGS should be revised to check the shift after adding globalOrder

SQL_NODE_ARGS="nodes.idNum, nodes.parent, nodes.depth, nodes.globalOrder"
SQL_NODE_COLS=(SQL_NODE_ARGS, SQL_NODE_ARGS+", nodes.content", 
  SQL_NODE_ARGS+", tags.name, nodesTags.param, tags.flags",
  SQL_NODE_ARGS+", nodes.content"+", tags.name, nodesTags.param, tags.flags")

SQL_GET_CHILD_NODES=( \
  """SELECT %s FROM nodes WHERE parent=? ORDER BY globalOrder""" % SQL_NODE_ARGS,
  """SELECT %s FROM nodes WHERE parent=? ORDER BY globalOrder""" % SQL_NODE_COLS[WITH_CONTENT],
  """SELECT %s FROM nodes LEFT OUTER JOIN nodesTags ON nodes.idNum = nodesTags.nodeIdNum LEFT OUTER JOIN tags on nodesTags.tagIdNum=tags.idNum WHERE nodes.parent=? ORDER BY nodes.globalOrder""" % SQL_NODE_COLS[WITH_TAGS],
  """SELECT %s FROM nodes LEFT OUTER JOIN nodesTags ON nodes.idNum = nodesTags.nodeIdNum LEFT OUTER JOIN tags on nodesTags.tagIdNum=tags.idNum WHERE nodes.parent=? ORDER BY nodes.globalOrder""" % SQL_NODE_COLS[WITH_CONTENT_AND_TAGS]
)

SQL_TAG="""INSERT OR REPLACE INTO nodesTags (tagIdNum,nodeIdNum,param) SELECT tags.IdNum,?,? FROM tags WHERE tags.name = ? LIMIT 1"""
SQL_CLEAR_TAGS_ON_NODE="""DELETE FROM nodesTags WHERE tags.name = ?"""

SQL_GET_NODE_BY_IDNUM=( \
  """SELECT %s FROM nodes WHERE idNum=? ORDER BY globalOrder""" % SQL_NODE_ARGS,
  """SELECT %s FROM nodes WHERE idNum=? ORDER BY globalOrder""" % SQL_NODE_COLS[1],
)

# node slices
SQL_GET_NODES_SLICE=( \
  """SELECT %s FROM nodes WHERE globalOrder>? AND globalOrder<? ORDER BY globalOrder""" % SQL_NODE_ARGS,
  """SELECT %s FROM nodes WHERE globalOrder>? AND globalOrder<? ORDER BY globalOrder""" % SQL_NODE_COLS[WITH_CONTENT],
  """SELECT %s FROM nodes LEFT OUTER JOIN nodesTags ON nodes.idNum = nodesTags.nodeIdNum LEFT OUTER JOIN tags on nodesTags.tagIdNum=tags.idNum WHERE nodes.globalOrder>? AND nodes.globalOrder<? ORDER BY nodes.globalOrder""" % SQL_NODE_COLS[WITH_TAGS],
  """SELECT %s FROM nodes LEFT OUTER JOIN nodesTags ON nodes.idNum = nodesTags.nodeIdNum LEFT OUTER JOIN tags on nodesTags.tagIdNum=tags.idNum WHERE nodes.globalOrder>? AND nodes.globalOrder<? ORDER BY nodes.globalOrder""" % SQL_NODE_COLS[WITH_CONTENT_AND_TAGS]
)
SQL_GET_UNBOUNDED_NODES_SLICE=(
  """SELECT %s FROM nodes WHERE globalOrder>? ORDER BY globalOrder""" % SQL_NODE_ARGS,
  """SELECT %s FROM nodes WHERE globalOrder>? ORDER BY globalOrder""" % SQL_NODE_COLS[WITH_CONTENT],
  """SELECT %s FROM nodes LEFT OUTER JOIN nodesTags ON nodes.idNum = nodesTags.nodeIdNum LEFT OUTER JOIN tags on nodesTags.tagIdNum=tags.idNum WHERE nodes.globalOrder>? ORDER BY nodes.globalOrder""" % SQL_NODE_COLS[WITH_TAGS],
  """SELECT %s FROM nodes LEFT OUTER JOIN nodesTags ON nodes.idNum = nodesTags.nodeIdNum LEFT OUTER JOIN tags on nodesTags.tagIdNum=tags.idNum WHERE nodes.globalOrder>? ORDER BY nodes.globalOrder""" % SQL_NODE_COLS[WITH_CONTENT_AND_TAGS]
)

# tagged children node
SQL_GET_TAGGED_CHILD_NODES=( \
  """SELECT %s FROM nodes LEFT OUTER JOIN nodesTags ON nodes.idNum = nodesTags.nodeIdNum LEFT OUTER JOIN tags on nodesTags.tagIdNum=tags.idNum WHERE nodes.parent=? AND tags.name=? ORDER BY nodes.globalOrder""" % SQL_NODE_ARGS,
  """SELECT %s FROM nodes LEFT OUTER JOIN nodesTags ON nodes.idNum = nodesTags.nodeIdNum LEFT OUTER JOIN tags on nodesTags.tagIdNum=tags.idNum WHERE nodes.parent=? AND tags.name=? ORDER BY nodes.globalOrder""" % SQL_NODE_COLS[1]
)
# tagged node slices
SQL_GET_TAGGED_NODES_SLICE=( \
  """SELECT %s FROM nodes LEFT OUTER JOIN nodesTags ON nodes.idNum = nodesTags.nodeIdNum LEFT OUTER JOIN tags on nodesTags.tagIdNum=tags.idNum WHERE tags.name=? AND nodes.globalOrder>? AND nodes.globalOrder<? ORDER BY nodes.globalOrder""" % SQL_NODE_ARGS,
  """SELECT %s FROM nodes LEFT OUTER JOIN nodesTags ON nodes.idNum = nodesTags.nodeIdNum LEFT OUTER JOIN tags on nodesTags.tagIdNum=tags.idNum WHERE tags.name=? AND nodes.globalOrder>? AND nodes.globalOrder<? ORDER BY nodes.globalOrder""" % SQL_NODE_COLS[1]
)
SQL_GET_UNBOUNDED_TAGGED_NODES_SLICE=( \
  """SELECT %s FROM nodes LEFT OUTER JOIN nodesTags ON nodes.idNum = nodesTags.nodeIdNum LEFT OUTER JOIN tags on nodesTags.tagIdNum=tags.idNum WHERE tags.name=? AND nodes.globalOrder>? ORDER BY nodes.globalOrder""" % SQL_NODE_ARGS,
  """SELECT %s FROM nodes LEFT OUTER JOIN nodesTags ON nodes.idNum = nodesTags.nodeIdNum LEFT OUTER JOIN tags on nodesTags.tagIdNum=tags.idNum WHERE tags.name=? AND nodes.globalOrder>? ORDER BY nodes.globalOrder""" % SQL_NODE_COLS[1])

# get tagged node slices by param value
SQL_GET_NODES_BY_TAG_VALUE=( \
  """SELECT %s FROM nodes LEFT OUTER JOIN nodesTags ON nodes.idNum = nodesTags.nodeIdNum LEFT OUTER JOIN tags on nodesTags.tagIdNum=tags.idNum WHERE tags.name=? AND nodesTags.param=? ORDER BY nodes.globalOrder""" % SQL_NODE_ARGS,
  """SELECT %s FROM nodes LEFT OUTER JOIN nodesTags ON nodes.idNum = nodesTags.nodeIdNum LEFT OUTER JOIN tags on nodesTags.tagIdNum=tags.idNum WHERE tags.name=? AND nodesTags.param=? ORDER BY nodes.globalOrder""" % SQL_NODE_COLS[1])

# get prev/next tagged node
SQL_GET_PREV_TAGGED_NODE=( \
  """SELECT %s FROM nodes LEFT OUTER JOIN nodesTags ON nodes.idNum = nodesTags.nodeIdNum LEFT OUTER JOIN tags on nodesTags.tagIdNum=tags.idNum WHERE nodes.globalOrder<? and tags.name=? ORDER BY nodes.globalOrder DESC LIMIT 1""" % SQL_NODE_ARGS,
  """SELECT %s FROM nodes LEFT OUTER JOIN nodesTags ON nodes.idNum = nodesTags.nodeIdNum LEFT OUTER JOIN tags on nodesTags.tagIdNum=tags.idNum WHERE nodes.globalOrder<? and tags.name=? ORDER BY nodes.globalOrder DESC LIMIT 1""" % SQL_NODE_COLS[1])
SQL_GET_NEXT_TAGGED_NODE=( \
  """SELECT %s FROM nodes LEFT OUTER JOIN nodesTags ON nodes.idNum = nodesTags.nodeIdNum LEFT OUTER JOIN tags on nodesTags.tagIdNum=tags.idNum WHERE nodes.globalOrder>? and tags.name=? ORDER BY nodes.globalOrder LIMIT 1""" % SQL_NODE_ARGS,
  """SELECT %s FROM nodes LEFT OUTER JOIN nodesTags ON nodes.idNum = nodesTags.nodeIdNum LEFT OUTER JOIN tags on nodesTags.tagIdNum=tags.idNum WHERE nodes.globalOrder>? and tags.name=? ORDER BY nodes.globalOrder LIMIT 1""" % SQL_NODE_COLS[1])

# get tagged child nodes
SQL_GET_TAGGED_CHILD_NODES=( \
  """SELECT %s FROM nodes LEFT OUTER JOIN nodesTags ON nodes.idNum = nodesTags.nodeIdNum LEFT OUTER JOIN tags on nodesTags.tagIdNum=tags.idNum WHERE nodes.parent=? and tags.name=? ORDER BY nodes.globalOrder""" % SQL_NODE_ARGS,
  """SELECT %s FROM nodes LEFT OUTER JOIN nodesTags ON nodes.idNum = nodesTags.nodeIdNum LEFT OUTER JOIN tags on nodesTags.tagIdNum=tags.idNum WHERE nodes.parent=? and tags.name=? ORDER BY nodes.globalOrder""" % SQL_NODE_COLS[1])


SQL_GET_GLOBAL_ORDER="""SELECT globalOrder,depth FROM nodes WHERE idNum=? LIMIT 1"""
SQL_GET_DESC_UPPER_BOUND="""SELECT globalOrder FROM nodes WHERE globalOrder>? AND depth<=? ORDER BY globalOrder LIMIT 1"""
SQL_GET_SIBLING_GLOBAL_ORDER="""SELECT globalOrder FROM nodes WHERE parent=? and globalOrder>? ORDER BY globalOrder LIMIT 1"""
SQL_GET_LAST_GLOBAL_ORDER="""SELECT globalOrder FROM nodes ORDER BY globalOrder DESC LIMIT 1"""
SQL_DROP_DESC_NODES=["""DELETE FROM nodes WHERE globalOrder>? AND globalOrder<?""",
  """DELETE FROM nodes WHERE globalOrder>=? AND globalOrder<?"""]
SQL_DROP_TAIL_NODES=["""DELETE FROM nodes WHERE globalOrder>?""",
  """DELETE FROM nodes WHERE globalOrder>=?"""]
SQL_APPEND_NODE=["""INSERT INTO nodes (content,parent,globalOrder,depth) VALUES (?,?,?,?)""",
"""INSERT INTO tmp_nodes (content,parent,globalOrder,depth) VALUES (?,?,?,?)"""]
# SQL tags commands
SQL_ADD_TAG="INSERT OR REPLACE INTO tags (name, comment, flags, parent,relation) VALUES (?,?,?,-1,-1)"

# modified:
#  SQL_GET_NODE_BY_IDNUM
#  SQL_GET_CHILD_NODES
#  SQL_GET_NODES_SLICE
#  SQL_GET_UNBOUNDED_NODES_SLICE
#  SQL_GET_TAGGED_CHILD_NODES
#  SQL_GET_TAGGED_NODES_SLICE
#  SQL_GET_UNBOUNDED_TAGGED_NODES_SLICE
# removed:
#  SQL_GET_CHILD_NODES_AND_TAGS
#  SQL_GET_NODES_SLICE_AND_TAGS
#  SQL_GET_UNBOUNDED_NODES_SLICE_AND_TAGS
# TODO:
#  make SQL_GET_NODE_BY_IDNUM capable of pre-loading tags (is this really needed??)


