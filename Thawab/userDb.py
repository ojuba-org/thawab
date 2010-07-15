# -*- coding: UTF-8 -*-
"""
The meta handling classes of thawab
Copyright © 2008-2010, Muayyad Alsadi <alsadi@ojuba.org>

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
import sys, os, os.path, re, sqlite3, time, threading

#################################################

USER_DB_SCHEMA="""\
CREATE TABLE "starred" (
	"kitab" TEXT PRIMARY KEY,
	"time" FLOAT
);

CREATE INDEX StarredTimeIndex on starred(time);

CREATE TABLE "bookmarks" (
	"kitab" TEXT,
	"version" TEXT,
	"globalOrder" INTEGER,
	"nodeIdNum" INTEGER,
	"nodeId" TEXT,
	"title" TEXT,
	"time" FLOAT,
	PRIMARY KEY ("kitab", "version", nodeId)
);

CREATE INDEX BookmarksKitabIndex on bookmarks(kitab);
CREATE INDEX BookmarksNodeIdNumIndex on bookmarks(nodeIdNum);
CREATE INDEX BookmarksGlobalOrderIndex on bookmarks(globalOrder);
CREATE INDEX BookmarksTimeIndex on bookmarks(time);

CREATE TABLE "comments" (
	"kitab" TEXT,
	"version" TEXT,
	"globalOrder" INTEGER,
	"nodeIdNum" INTEGER,
	"nodeId" TEXT,
	"title" TEXT,
	"comment" TEXT,
	"time" FLOAT,
	PRIMARY KEY ("kitab", "version", nodeId)
);

CREATE INDEX CommentsKitabIndex on comments(kitab);
CREATE INDEX CommentsNodeIdNumIndex on comments(nodeIdNum);
CREATE INDEX CommentsGlobalOrderIndex on comments(globalOrder);
CREATE INDEX CommentsTimeIndex on comments(time);

"""
SQL_GET_ALL_STARRED="""SELECT kitab FROM starred ORDER BY time"""
SQL_GET_STARRED_TIME="""SELECT time FROM starred WHERE kitab=?"""
SQL_SET_STARRED='INSERT OR REPLACE INTO starred (kitab, time) VALUES (?, ?)'
SQL_UNSET_STARRED='DELETE OR IGNORE FROM starred WHERE kitab=?'

# NOTE: globalOrder is used to get the right book order
# NOTE: nodeIdNum is used for consistancy checking and optimization

SQL_GET_ALL_BOOKMARKS="""SELECT * FROM bookmarks ORDER BY kitab"""
SQL_GET_BOOKMARKED_KUTUB="""SELECT DISTINCT kitab FROM bookmarks ORDER BY kitab"""
SQL_GET_KITAB_BOOKMARKS="""SELECT * FROM bookmarks WHERE kitab=? ORDER BY time"""
SQL_ADD_BOOKMARK='INSERT OR REPLACE INTO bookmarks (kitab, version, globalOrder, nodeIdNum, nodeId, title, time) VALUES (?,?,?,?,?,?,?)'

SQL_GET_ALL_COMMENTS="""SELECT * FROM comments ORDER BY kitab"""
SQL_GET_COMMENTED_KUTUB="""SELECT DISTINCT kitab FROM comments ORDER BY kitab"""
SQL_GET_KITAB_COMMENTS="""SELECT * FROM comments WHERE kitab=? ORDER BY time"""
SQL_ADD_COMMENT='INSERT OR REPLACE INTO comments (kitab, version, globalOrder, nodeIdNum, nodeId, title, comment, time) VALUES (?,?,?,?,?,?,?,?)'

#################################

class UserDb(object):
  """a class holding metadata cache"""
  def __init__(self, th, user_db):
    self.th=th
    self.db_fn=user_db
    if not os.path.exists(self.db_fn): create_new=True
    else: create_new=False
    self._cn={}
    cn=self._getConnection()
    if create_new:
      cn.executescript(USER_DB_SCHEMA)
      cn.commit()

  def _getConnection(self):
    n = threading.current_thread().name
    if self._cn.has_key(n):
      r = self._cn[n]
    else:
      r = sqlite3.connect(self.db_fn)
      r.row_factory=sqlite3.Row
      self._cn[n] = r
    return r

  def getStarredTime(self, kitab):
    """
    return None if not starred, can be used to check if starred
    """
    r = self._getConnection().execute(SQL_GET_STARRED_TIME, (kitab,)).fetchone()
    if not r: return None
    return r['time']

  def getStarredList(self):
    r = self._getConnection().execute(SQL_GET_ALL_STARRED).fetchall()
    return map(lambda i: i['kitab'], r)

  def starKitab(self, kitab):
    self._getConnection().execute(SQL_SET_STARRED , (kitab, float(time.time())))

  def unstarKitab(self, kitab):
    self._getConnection().execute(SQL_UNSET_STARRED, (kitab,))

  def starKitab(self, kitab):
    self._getConnection().execute(SQL_SET_STARRED , (kitab, float(time.time())))

  def getAllBookmarks(self):
    r = self._getConnection().execute(SQL_GET_ALL_BOOKMARKS).fetchall()
    return map(lambda i: dict(i), r)

  def getBookmarkedKutub(self):
    r = self._getConnection().execute(SQL_GET_BOOKMARKED_KUTUB).fetchall()
    return map(lambda i: i['kitab'], r)

  def getKitabBookmarks(self, kitab):
    r = self._getConnection().execute(SQL_GET_KITAB_BOOKMARKS, (kitab, )).fetchall()
    return map(lambda i: dict(i), r)

  def addBookmark(self, kitab, version, globalOrder, nodeIdNum, nodeId, title):
    self._getConnection().execute(SQL_ADD_BOOKMARKS, (kitab, version, globalOrder, nodeIdNum, nodeId, title, float(time.time()) ))

  def getAllComments(self):
    r = self._getConnection().execute(SQL_GET_ALL_COMMENTS).fetchall()
    return map(lambda i: dict(i), r)

  def getCommentedKutub(self):
    r = self._getConnection().execute(SQL_GET_COMMENTED_KUTUB).fetchall()
    return map(lambda i: i['kitab'], r)

  def getKitabComments(self, kitab):
    r = self._getConnection().execute(SQL_GET_KITAB_COMMENTS, (kitab, )).fetchall()
    return map(lambda i: dict(i), r)

  def addComment(self, kitab, version, globalOrder, nodeIdNum, nodeId, title, comment):
    self._getConnection().execute(SQL_ADD_COMMENT, (kitab, version, globalOrder, nodeIdNum, nodeId, title, comment, float(time.time()) ))


