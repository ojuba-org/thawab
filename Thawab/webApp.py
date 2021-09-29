# -*- coding: UTF-8 -*-
"""

Copyright © 2009, Muayyad Alsadi <alsadi@ojuba.org>

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

import sys, os, os.path
import hashlib
import time
import bisect
import base64
from html import escape # for html escaping
from .meta import prettyId, makeId, metaVrr
from .stemming import normalize_tb
from .okasha.utils import ObjectsCache
from .okasha.baseWebApp import *
from .okasha.bottleTemplate import bottleTemplate

# fixme move this to okasha.utils
def tryInt(s, d = 0):
    try:
        return int(s)
    except ValueError:
        pass
    except TypeError:
        pass
    return d

class webApp(baseWebApp):
    _emptyViewResp = {
        'apptype': 'web',
        'content': '', 'childrenLinks': '',
        'prevUrl': '', 'prevTitle': '',
        'upUrl': '', 'upTitle': '',
        'nextUrl': '', 'nextTitle': '',
        'breadcrumbs': ''
    }
    def __init__(self, th, typ = 'web', *args, **kw):
        """
            th is an instance of ThawabMan
            allowByUri = True for desktop, False for server
        """
        self.th = th
        self.isMonolithic = th.isMonolithic
        self.stringSeed = "S3(uR!r7y"
        self._typ = typ
        self._allowByUri = (typ == 'app')
        self._emptyViewResp["apptype"]=self._typ
        # FIXME: move ObjectsCache of kitab to routines to core.ThawabMan
        if not self.isMonolithic:
            import threading
            lock1 = threading.Lock();
        else:
            lock1 = None
        self.searchCache = ObjectsCache(lock = lock1)
        baseWebApp.__init__(self, *args, **kw)

    def _safeHash(self,o):
        """
            a URL safe hash, it results a 22 byte long string hash based on md5sum
        """
        if isinstance(o,str): o = o.encode('utf8')
        if isinstance(self.stringSeed,str): self.stringSeed = self.stringSeed.encode('utf8')
        s=base64.b64encode(hashlib.md5(self.stringSeed+o).digest()).decode()[:22]
        #return hashlib.md5(self.stringSeed+o).digest().encode('base64').replace('+','-').replace('/','_')[:22]
        return s

    def _root(self, rq, *args):
        if args:
            if args[0] == 'favicon.ico':
                raise redirectException(rq.script+'/_files/img/favicon.ico')
            elif args[0] == 'robots.txt':
                return self._robots(rq, *args)
            elif args[0] == 'sitemap.xml':
                return self._sitemap(rq, *args)
            raise forbiddenException()
        raise redirectException(rq.script+'/index/')

    @expose(contentType = 'text/plain; charset = utf-8')
    def _robots(self, rq, *args):
        return """Sitemap: http://%s/sitemap.xml
User-agent: *
Allow: /
""" % (rq.environ['HTTP_HOST']+rq.script)

    @expose(contentType = 'text/xml; charset = utf-8')
    def _sitemap(self, rq, *args):
        t = time.gmtime() # FIXME: use meta to get mime of meta.db
        d = time.strftime("%Y-%m-%dT%H:%M:%S+00:00", t)
        tmp = "\t<url>\n\t\t<loc>http://"+rq.environ['HTTP_HOST']+rq.script+"/static/%s/_i0.html</loc>\n\t\t<lastmod>"+d+"</lastmod>\n\t\t<changefreq>daily</changefreq>\n\t\t<priority>0.5</priority>\n\t</url>"
        l=self.th.getMeta().getKitabList()
        urls=[]
        for k in l:
            urls.append(tmp % (k))
        return """<?xml version='1.0' encoding='UTF-8'?>
<urlset xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" xsi:schemaLocation="http://www.sitemaps.org/schemas/sitemap/0.9 http://www.sitemaps.org/schemas/sitemap/0.9/sitemap.xsd" xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
    <url>
        <loc>http://thawab.ojuba.org/index/</loc>
        <lastmod>%s</lastmod>
        <changefreq>daily</changefreq>
        <priority>0.8</priority>
    </url>
    %s
</urlset>""" % (d,"\n".join(urls))


    @expose(bottleTemplate,["main"])
    def index(self, rq, *args):
        rq.q.title = "الرئيسية"
        l = self.th.getMeta().getKitabList()
        htmlLinks = []
        l = sorted(l)
        for k in l:
            # FIXME: it currenly offers only one version for each kitab (the first one)
            htmlLinks.append('\t<li><a href="/view/%s/">%s</a></li>' % (k,
            prettyId(self.th.getMeta().getByKitab(k)[0]['kitab'])))
        htmlLinks = ("\n".join(htmlLinks))
        return {
            "lang":"ar", "dir":"rtl",
            "kutublinks": htmlLinks,
            "args":'/'.join(args)}

    @expose(percentTemplate,["stem.html"])
    def stem(self, rq, *args):
        from .stemming import stemArabic
        w = rq.q.getfirst('word','').decode('utf-8')
        s = ''
        if w:
            s = " ".join([stemArabic(i) for i in w.split()])
        return {"script":rq.script, "word":w, "stem":s}

    def _getKitabObject(self, rq, *args):
        # FIXME: cache KitabObjects and update last access
        if not args: raise forbiddenException() # TODO: make it a redirect to index
        k = args[0]
        if k == '_by_uri':
            if self._allowByUri:
                uri = rq.q.getfirst('uri',None)
                if not uri:
                    raise fileNotFoundException()
                m = self.th.getMeta().getByUri(uri)
            else:
                raise forbiddenException()
        else:
            m = self.th.getMeta().getLatestKitab(k)
            if not m:
                raise forbiddenException()
            uri = m['uri']
        ki = self.th.getCachedKitab(uri)
        return ki, m

    def _view(self, ki, m, i, d = '#', s = ""):
        r = self._emptyViewResp.copy()
        node, p, u, n, c, b = ki.toc.getNodePrevUpNextChildrenBreadcrumbs(i)
        if n:
            ub = n.globalOrder
        else:
            ub = -1
        if not node or i == "_i0":
            r['content'] = "<h1>%s</h1>" % escape(prettyId(m['kitab']))
        else:
            r['content'] = node.toHtml(ub).replace('\n\n','\n</p><p>\n')
        if c:
            cLinks = ''.join(['<li><a href = "%s">%s</a></li>\n' % \
                                             (d + "_i" + str(cc.idNum) + s,
                                              escape(cc.getContent())) for cc in c])
            cLinks = "<ul>\n" + cLinks + "</ul>"
        else:
            cLinks = ''
        r['childrenLinks'] = cLinks
        if n:
            r['nextUrl'] = d + '_i' + str(n.idNum) + s
            r['nextTitle'] = escape(n.getContent())
        if p:
            r['prevUrl'] = d + '_i' + str(p.idNum) + s
            r['prevTitle'] = escape(p.getContent())
        if u:
            r['upUrl'] = d + '_i' + str(u.idNum) + s
            r['upTitle'] = escape(u.getContent())
        if b:
            r['breadcrumbs'] = " &gt; ".join([("<a href = '" + \
                                                                 d + \
                                                                 "_i%i" + \
                                                                 s + \
                                                                 "'>%s</a>") % \
                                                                 (i_t[0], escape(i_t[1])) for i_t in b])
        vrr = metaVrr(ki.meta)
        #self.th.searchEngine.related(m['kitab'], vrr, node.idNum)
        return r

    def _get_kitab_details(self, rq, *args):
        ki, m = self._getKitabObject(rq, *args)
        if not ki or not m:
            return None, None, {}
        lang = m.get('lang', 'ar')
        if lang in ('ar', 'fa', 'he'):
            d = 'rtl'
        else:
            d = 'ltr'
        kitabId = escape(makeId(m['kitab']))
        t = escape(prettyId(m['kitab']))
        r = self._emptyViewResp.copy()
        r.update({
            "script": rq.script,
            "kitabTitle": t,
            "kitabId": kitabId,
            "headingId": "_i0",
            "app": "Thawab", "version": "3.0.1",
            "lang": lang, "dir": d,
            "title": t,
            "content": t,
            "args": '/'.join(args)})
        return ki, m, r


    @expose(bottleTemplate,["view"])
    def static(self, rq, *args):
        l = len(args)
        if l < 1:
            raise forbiddenException() # TODO: make it show a list of books
        elif l == 1:
            raise redirectException(rq.script + '/static/' + args[0] + "/_i0.html")
        elif l != 2:
            raise forbiddenException()
        ki, m, r = self._get_kitab_details(rq, *args)
        if not ki:
            raise fileNotFoundException()
        h = args[1]
        if h.endswith(".html"):
            h = h[:-5]
        r.update(self._view(ki, m, h, './', ".html"))
        if self.th.searchEngine.getIndexedVersion(m['kitab']):
            rq.q.is_indexed = 1
            r['is_indexed'] = 1
        else:
            rq.q.is_indexed = 0
            r['is_indexed'] = 0
        r['is_static'] = 1
        r['d'] = './'
        r['s'] = '.html'
        return r

    @expose(bottleTemplate,["view"])
    def view(self, rq, *args):
        if len(args) != 1:
            raise forbiddenException()
        ki, m, r = self._get_kitab_details(rq, *args)
        if not ki:
            raise fileNotFoundException()
        if self.th.searchEngine.getIndexedVersion(m['kitab']):
            rq.q.is_indexed = 1
            r['is_indexed'] = 1
        else:
            rq.q.is_indexed = 0
            r['is_indexed'] = 0
        r['is_static'] = 0
        r['d'] = '#'
        r['s'] = ''
        return r

    @expose()
    def ajax(self, rq, *args):
        if not args:
            raise forbiddenException()
        if args[0] == 'searchExcerpt' and len(args) == 3:
            h = args[1]
            try:
                i = int(args[2])
            except TypeError:
                raise forbiddenException()
            R = self.searchCache.get(h)
            if R == None:
                return 'انتهت صلاحية هذا البحث'
            try :
                r = self.th.searchEngine.resultExcerpt(R, i)
            except OSError as e:
                print('** webapp.ajax: %s' , e)
                return ''
            #r = escape(self.th.searchEngine.resultExcerpt(R,i)).replace('\0','<em>').replace('\010','</em>').replace(u"\u2026",u"\u2026<br/>").encode('utf8')
            return r
        elif args[0] == 'kutub' and len(args) == 1:
            q = rq.q.getfirst('q','').strip().translate(normalize_tb)
            r = []
            l = self.th.getMeta().getKitabList()
            l = sorted(l)
            for k in l:
                n = prettyId(k)
                if not q or q in n.translate(normalize_tb):
                    r.append('\t<li><a href="/view/%s/">%s</a></li>' % (k, n))
            return '<ul>%s</ul>\n<div class="clear"></div>' % "\n".join(r)
        raise forbiddenException()
    
    @expose(jsonDumps)
    def json(self, rq, *args):
        # use rq.rhost to impose host-based limits on searching
        if not args: raise forbiddenException()
        ki = None
        r = {}
        if args[0] == 'view':
            a = args[1:]
            ki, m = self._getKitabObject(rq, *a)
            if len(a) == 2:
                r = self._view(ki, m, a[1])
        elif args[0] == 'search':
            q = rq.q.getfirst('q','')
            h = self._safeHash(q)
            # FIXME: check to see if one already search for that before
            if not isinstance(q, str): q = q.decode('utf8')
            R = self.th.searchEngine.queryIndex(q)
            # print R
            if not R:
                return {'t': 0, 'c': 0, 'h': ''}
            self.searchCache.append(h,R)
            r = {'t': R.runtime, 'c': len(R), 'h': h}
        elif args[0] == 'searchResults':
            h = rq.q.getfirst('h','')
            try:
                i = int(rq.q.getfirst('i', '0'))
            except TypeError:
                i = 0
            try:
                c = int(rq.q.getfirst('c', '0'))
            except TypeError:
                c = 0
            R = self.searchCache.get(h)
            if R == None:
                return {'c': 0}
            C = len(R)
            if i >= C:
                return {'c': 0}
            c = min(c, C-i)
            r = {'c': c, 'a': []}
            n = 100.0 / R[0].score
            j = 0
            for j in range(i, i + c):
                name = R[j]['kitab']
                v = R[j]['vrr'].split('-')[0]
                m = self.th.getMeta().getLatestKitabV(name,v)
                k = m['kitab'] #.replace('_', ' ')
                if not m:
                    continue # book is removed
                r['a'].append({
                'i':j,'n':'_i'+R[j]['nodeIdNum'],
                'k':k, 'a':prettyId(m['author']), 'y':tryInt(m['year']),
                't':R[j]['title'], 'r':'%4.1f' % (n*R[j].score)})
                j += 1
            r[c] = j;
        else:
            r = {}
        return r

