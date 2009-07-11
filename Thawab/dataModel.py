# -*- coding: utf-8 -*-
"""
The string constants to handle the data model
Copyright © 2008, Muayyad Alsadi <alsadi@ojuba.org>

    Released under terms on Waqf Public License.
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

SQL_DATA_MODEL="""\
CREATE TABLE "meta" (
	"repo" TEXT,
	"kitab" TEXT,
	"version" TEXT,
	"releaseMajor" TEXT,
	"releaseMinor" TEXT,
	"author" TEXT,
	"year" TEXT,
	"originalYear" TEXT,
	"classification" TEXT
);

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
	"type" INTEGER NOT NULL,
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

CREATE INDEX MetaKitabIndex on meta (kitab);
CREATE INDEX MetaKitabVersionIndex on meta (kitab,version);
CREATE INDEX MetaKitabRelease1Index on meta (kitab,version,release1);
CREATE INDEX MetaFullKitabIndex on meta (kitab,version,release1,release2);
CREATE INDEX MetaAuthorIndex on meta (author);
CREATE INDEX MetaYearIndex on meta (year);
CREATE INDEX MetaClassificationIndex on meta (classification);

CREATE INDEX NodesParentIndex on nodes (parent);
CREATE INDEX NodesNodesGlobalOrderIndex on nodes (globalOrder);
CREATE INDEX NodesDepthIndex on nodes (depth);

CREATE INDEX NodesTagTagIdNumIndex on nodesTags(tagIdNum);
CREATE INDEX NodesTagNodeIdNumIndex on nodesTags(nodeIdNum);
CREATE INDEX NodesTagParamIndex on nodesTags(param);
CREATE INDEX TagsName on tags (name);

"""
#################################################
# arguments to make the built-in tags
STD_TAGS_ARGS=( \
  # (name, comment, type, parent, relation)
  ("header", "an anchor that marks header in TOC.",TAGTYPE_POS_BLOCK | TAGTYPE_FLAGS_HEADER),
  ("textbody", "a tag that marks a typical text.",0),
  # the following index-tags marks the header
  ("hadith.authenticity", "marks the authenticity of the hadith, param values are Sahih, Hasan, weak, fabricated", TAGTYPE_IX_TAG),
  # new index field for rawi
  ("hadith.ruwah.rawi", "marks a rawi", TAGTYPE_FLAGS_IX_FIELD),
  # the following index-tags marks the rawi field
  ("hadith.ruwah.authenticity", "marks the authenticity of the rawi, param values are thiqah, ...,kathoob", TAGTYPE_IX_TAG),
  ("hadith.ruwah.tabaqa", "marks the tabaqa of the rawi, param values are sahabi,tabii,...", TAGTYPE_IX_TAG)
)
STD_TAGS_HASH=dict(map(lambda i: (i[0],i),STD_TAGS_ARGS))
# ENUMs
WITH_NONE=0
WITH_CONTENT=1
WITH_TAGS=2
WITH_CONTENT_AND_TAGS=3
#################################################
# SQL statements for manipulating the dataModel
SQL_GET_ALL_TAGS="""SELECT name,type,comment,parent,relation FROM tags"""
SQL_GET_NODE_CONTENT="""SELECT content from nodes WHERE idNum=? LIMIT 1"""

SQL_GET_NODE_TAGS="""SELECT tags.name,nodesTags.param FROM nodesTags LEFT OUTER JOIN tags on nodesTags.tagIdNum=tags.idNum WHERE nodesTags.nodeIdNum=? LIMIT 1"""

SQL_NODE_ARGS="nodes.idNum, nodes.parent, nodes.depth"
SQL_NODE_COLS=(SQL_NODE_ARGS, SQL_NODE_ARGS+", nodes.content", 
  SQL_NODE_ARGS+", tags.name, nodesTags.param",
  SQL_NODE_ARGS+", nodes.content"+", tags.name, nodesTags.param")

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

# tagged chilren node
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

SQL_GET_GLOBAL_ORDER="""SELECT globalOrder,parent FROM nodes WHERE idNum=? LIMIT 1"""
SQL_GET_SIBLING_GLOBAL_ORDER="""SELECT globalOrder FROM nodes WHERE parent=? and globalOrder>? ORDER BY globalOrder LIMIT 1"""
SQL_GET_LAST_GLOBAL_ORDER="""SELECT globalOrder FROM nodes ORDER BY globalOrder DESC LIMIT 1"""
SQL_DROP_DESC_NODES=["""DELETE FROM nodes WHERE globalOrder>? AND globalOrder<?""",
  """DELETE FROM nodes WHERE globalOrder>=? AND globalOrder<?"""]
SQL_DROP_TAIL_NODES=["""DELETE FROM nodes WHERE globalOrder>?""",
  """DELETE FROM nodes WHERE globalOrder>=?"""]
SQL_APPEND_NODE=["""INSERT INTO nodes (content,parent,globalOrder,depth) VALUES (?,?,?,?)""",
"""INSERT INTO tmp_nodes (content,parent,globalOrder,depth) VALUES (?,?,?,?)"""]
# SQL tags commands
SQL_ADD_TAG="INSERT OR REPLACE INTO tags (name, comment, type, parent,relation) VALUES (?,?,?,-1,-1)"

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


