# -*- coding: UTF-8 -*-
"""
gtkUi - gtk interface for thawab

Copyright © 2009-2010, Muayyad Alsadi <alsadi@ojuba.org>

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
import sys, os, os.path, time, re, sqlite3

import shutil, tempfile
import threading, socket
import gettext
import gobject
import glib, gtk, pango
import webkit

from urllib import unquote

import Thawab.core

from Thawab.webApp import webApp
from Thawab.shamelaUtils import ShamelaSqlite, shamelaImport
from paste import httpserver

class ThWV(webkit.WebView):
  def __init__(self):
    webkit.WebView.__init__(self)
    self.set_full_content_zoom(True)
    self.connect_after("populate-popup", self.populate_popup)
    #self.connect("resource-request-starting", self.test)

  #def test(self, *args,**kw):
  #  print "*"

  def populate_popup(self, view, menu):
    menu.append(gtk.SeparatorMenuItem())
    i = gtk.ImageMenuItem(gtk.STOCK_ZOOM_IN)
    i.connect('activate', lambda *a,**k: self.zoom_in())
    menu.append(i)
    i = gtk.ImageMenuItem(gtk.STOCK_ZOOM_OUT)
    i.connect('activate', lambda *a,**k: self.zoom_out())
    menu.append(i)
    i = gtk.ImageMenuItem(gtk.STOCK_ZOOM_100)
    i.connect('activate', lambda *a,**k: web_view.get_zoom_level() == 1.0 or self.set_zoom_level(1.0))
    menu.append(i)

    menu.show_all()
    return False

targets_l=gtk.target_list_add_uri_targets()

class ThImportWindow(gtk.Window):
  def __init__(self, main):
    gtk.Window.__init__(self)
    self.progress_phase = 0
    self.progress_books_in_file = 0
    self.progress_element = 0
    self.add_dlg = None
    self.drag_dest_set(gtk.DEST_DEFAULT_ALL,targets_l,(1<<5)-1)
    self.connect('drag-data-received', self.drop_data_cb)
    self.set_title(_('Import Shamela .bok files'))
    self.set_type_hint(gtk.gdk.WINDOW_TYPE_HINT_DIALOG)
    self.set_modal(True)
    self.set_transient_for(main)
    self.main=main
    self.connect('delete-event', lambda w,*a: w.hide() or True)
    
    vb=gtk.VBox(False,2); self.add(vb)
    hb0=gtk.HBox(False,2)
    vb.pack_start(hb0,False, False, 2)
    self.tool=hb=gtk.HBox(False,2)
    hb0.pack_start(hb,False, False, 2)
    b=gtk.Button(stock=gtk.STOCK_ADD)
    b.connect('clicked', self.add_cb)
    hb.pack_start(b, False, False, 2)
    b=gtk.Button(stock=gtk.STOCK_REMOVE)
    b.connect('clicked', self.rm)
    hb.pack_start(b, False, False, 2)
    b=gtk.Button(stock=gtk.STOCK_CLEAR)
    b.connect('clicked', lambda *a: self.ls.clear())
    hb.pack_start(b, False, False, 2)
    b=gtk.Button(stock=gtk.STOCK_CONVERT)
    b.connect('clicked', self.start)
    hb.pack_start(b, False, False, 2)
    self.progress=gtk.ProgressBar()
    self.progress.set_fraction(0.0)
    hb0.pack_start(self.progress, True, True, 2)
    b=gtk.Button(stock=gtk.STOCK_STOP)
    b.connect('clicked', self.stop)
    hb0.pack_start(b, False, False, 2)

    self.ls = gtk.ListStore(str,str,float,int,str) # fn, basename, percent, pulse, label
    self.lsv=gtk.TreeView(self.ls)
    cells=[]
    cols=[]
    cells.append(gtk.CellRendererText())
    cols.append(gtk.TreeViewColumn('Files', cells[-1], text=1))
    cols[-1].set_sizing(gtk.TREE_VIEW_COLUMN_AUTOSIZE)
    cols[-1].set_resizable(True)
    cols[-1].set_expand(True)
    cells.append(gtk.CellRendererProgress())
    cols.append(gtk.TreeViewColumn('%', cells[-1], value=2,pulse=3,text=4))
    cols[-1].set_expand(False)
    self.lsv.set_headers_visible(True)
    self.lsv.get_selection().set_mode(gtk.SELECTION_MULTIPLE)

    for i in cols: self.lsv.insert_column(i, -1)

    scroll=gtk.ScrolledWindow()
    scroll.set_policy(gtk.POLICY_NEVER,gtk.POLICY_ALWAYS)
    scroll.add(self.lsv)
    vb.pack_start(scroll,True, True, 2)

    
    x=gtk.Expander(_("Advanced options"))
    vb.pack_start(x, False, False, 2)

    xvb=gtk.VBox(False,2); x.add(xvb)

    f=gtk.Frame(_('Performance tuning:')); xvb.add(f)
    fvb=gtk.VBox(False,2); f.add(fvb)
    hb=gtk.HBox(False,2); fvb.add(hb)

    self.in_mem=gtk.CheckButton(_('in memory'))
    self.in_mem.set_tooltip_text(_("faster but consumes more memory and harder to debug."))
    hb.pack_start(self.in_mem, False, False, 2)


    f=gtk.Frame('Version Control:'); xvb.add(f)
    fvb=gtk.VBox(False,2); f.add(fvb)
    hb=gtk.HBox(False,2); fvb.add(hb)

    hb.pack_start(gtk.Label(_('Release Major:')), False, False, 2)
    self.releaseMajor=gtk.SpinButton(gtk.Adjustment(0, 0, 10000, 1, 10, 0))
    hb.pack_start(self.releaseMajor, False, False, 2)
    hb.pack_start(gtk.Label(_('Release Minor:')), False, False, 2)
    self.releaseMinor=gtk.SpinButton(gtk.Adjustment(0, 0, 10000, 1, 10, 0))
    hb.pack_start(self.releaseMinor, False, False, 2)

    f=gtk.Frame('Footnotes:'); xvb.add(f)
    fvb=gtk.VBox(False,2); f.add(fvb)
    hb=gtk.HBox(False,2); fvb.add(hb)

    hb.pack_start(gtk.Label(_('Prefix:')), False, False, 2)
    self.ft_prefix = gtk.Entry()
    self.ft_prefix.set_text('(')
    self.ft_prefix.set_width_chars(3)
    hb.pack_start(self.ft_prefix, False, False, 2)

    hb.pack_start(gtk.Label(_('Suffix:')), False, False, 2)
    self.ft_suffix = gtk.Entry()
    self.ft_suffix.set_text(')')
    self.ft_suffix.set_width_chars(3)
    hb.pack_start(self.ft_suffix, False, False, 2)

    self.ft_at_line_start = gtk.CheckButton(_('only at line start'))
    hb.pack_start(self.ft_at_line_start, False, False, 2)

    hb=gtk.HBox(False,2); fvb.add(hb)
    hb.pack_start(gtk.Label(_('in between spaces:')), False, False, 2)
    self.ft_sp = [gtk.RadioButton(group=None, label=_('no spaces'))]
    self.ft_sp.append(gtk.RadioButton(group=self.ft_sp[0], label=_('optional white-space')))
    self.ft_sp.append(gtk.RadioButton(group=self.ft_sp[0], label=_('optional white-spaces')))
    for i in self.ft_sp: hb.pack_start(i, False, False, 2)

    f=gtk.Frame('Footnote anchors in body:'); xvb.add(f)
    fvb=gtk.VBox(False,2); f.add(fvb)
    hb=gtk.HBox(False,2); fvb.add(hb)

    hb.pack_start(gtk.Label(_('Prefix:')), False, False, 2)
    self.bft_prefix = gtk.Entry()
    self.bft_prefix.set_text('(')
    self.bft_prefix.set_width_chars(3)
    hb.pack_start(self.bft_prefix, False, False, 2)

    hb.pack_start(gtk.Label(_('Suffix:')), False, False, 2)
    self.bft_suffix = gtk.Entry()
    self.bft_suffix.set_text(')')
    self.bft_suffix.set_width_chars(3)
    hb.pack_start(self.bft_suffix, False, False, 2)

    hb=gtk.HBox(False,2); fvb.add(hb)
    hb.pack_start(gtk.Label(_('in between spaces:')), False, False, 2)
    self.bft_sp = [gtk.RadioButton(group=None, label=_('no spaces'))]
    self.bft_sp.append(gtk.RadioButton(group=self.bft_sp[0], label=_('optional white-space')))
    self.bft_sp.append(gtk.RadioButton(group=self.bft_sp[0], label=_('optional white-spaces')))
    for i in self.bft_sp: hb.pack_start(i, False, False, 2)

    # TODO: add options to specify version and revision
    # TODO: add options to specify wither to break by hno
    # TODO: add options for handling existing files (overwrite?)

    ft_at_line_start=False
    ft_prefix=u'('
    ft_suffix=u')'
    ft_sp=u'' # can be ur'\s?' or ur'\s*'
    body_footnote_re=re.escape(ft_prefix)+ft_sp+ur'(\d+)'+ft_sp+re.escape(ft_suffix)
    footnote_re=(ft_at_line_start and u'^\s*' or u'') + body_footnote_re
    ft_prefix_len=len(ft_prefix)
    ft_suffix_len=len(ft_suffix)
    #shamelaImport(cursor, sh, bkid, footnote_re=ur'\((\d+)\)', body_footnote_re=ur'\((\d+)\)', ft_prefix_len=1, ft_suffix_len=1):
    self.show_all()

  def element_pulse_cb(self, i):
    self.ls[(i,)][2]=0
    self.ls[(i,)][3]=int(abs(self.ls[(i,)][3])+1)
    gtk.main_iteration()

  def element_progress_cb(self, i, percent, text=None):
    l=self.ls[(i,)]
    l[2]=percent
    if text!=None: l[4]=text
    gtk.main_iteration()

  def progress_cb(self, msg, p, *d, **kw):
    # print " ** progress phase %d: [%g%% completed] %s" % (self.progress_phase, p, msg)
    i=self.progress_element
    N=len(self.ls)
    j=self.progress_book_in_file
    n=self.progress_books_in_file
    if n==0 or N==0: return
    if self.progress_phase==1:
      percent=p*0.25
    else:
      percent=(75.0/n)*j + p*0.75/n + 25.0
    
    if not kw.has_key('show_msg'): msg=_("working ...")
    self.element_progress_cb(i, percent, msg)
    self.progress.set_fraction( float(i)/N + percent/100.0/N )
    gtk.main_iteration()

  def start(self, b):
    self.tool.set_sensitive(False)

    ft_at_line_start=self.ft_at_line_start.get_active()
    ft_prefix=self.ft_prefix.get_text(); ft_prefix_len=len(ft_prefix)
    ft_suffix=self.ft_suffix.get_text(); ft_suffix_len=len(ft_suffix)
    ft_sp=[u'', ur'\s?' , ur'\s*'][ [i.get_active() for i in self.ft_sp].index(True) ]
    footnote_re=(ft_at_line_start and u'^\s*' or u'') + re.escape(ft_prefix)+ft_sp+ur'(\d+)'+ft_sp+re.escape(ft_suffix)

    bft_prefix=self.bft_prefix.get_text()
    bft_suffix=self.bft_suffix.get_text()
    bft_sp=[u'', ur'\s?' , ur'\s*'][ [i.get_active() for i in self.bft_sp].index(True) ]
    body_footnote_re=re.escape(bft_prefix)+bft_sp+ur'(\d+)'+bft_sp+re.escape(bft_suffix)

    if not self.in_mem.get_active():
      fh,db_fn = tempfile.mkstemp(suffix='.sqlite', prefix='th_shamela_tmp')
    else: db_fn=None
    for i,l in enumerate(self.ls):
      self.progress_element=i
      self.progress_book_in_file=0
      self.progress_books_in_file=1
      fn=l[0]
      if db_fn:
        f=open(db_fn, "w")
        f.truncate(0)
        f.close()
        cn=sqlite3.connect(db_fn, isolation_level=None)
      else:
        cn=None
      self.progress_phase=1
      try: sh=ShamelaSqlite(fn, cn, int(self.releaseMajor.get_value()), int(self.releaseMinor.get_value()), self.progress_cb)
      except TypeError: print "not a shamela file"; continue
      except OSError: print "mdbtools is not installed"; break
      sh.toSqlite()
      self.progress_phase=2
      ids=sh.getBookIds()
      self.progress_books_in_file=len(ids)
      for j, bkid in enumerate(ids):
        self.progress_book_in_file=j
        ki=self.main.th.mktemp()
        c=ki.seek(-1,-1)
        m=shamelaImport(c, sh, bkid, footnote_re, body_footnote_re, ft_prefix_len, ft_suffix_len)
        c.flush()
        t_fn=os.path.join(self.main.th.prefixes[0], 'db', u"".join((m['kitab'] + u"-" + m['version'] + Thawab.core.th_ext,)))
        print "moving %s to %s" % (ki.uri, t_fn)
        shutil.move(ki.uri, t_fn)
      self.progress_cb(_("Done"), 100.0, show_msg=True)

    if db_fn and os.path.exists(db_fn):
      try: os.unlink(db_fn)
      except OSError: pass
    #self.element_progress_cb(0, 25.0, "testing")
    self.tool.set_sensitive(True)

  def stop(self, b):
    self.tool.set_sensitive(True)

  def add_cb(self, b):
    if self.run_add_dlg()==gtk.RESPONSE_ACCEPT:
      for i in self.add_dlg.get_filenames(): self.add_fn(i)

  def run_add_dlg(self):
    if self.add_dlg:
      return self.add_dlg.run()
    self.add_dlg=gtk.FileChooserDialog(_("Select files to import"),buttons=(gtk.STOCK_CANCEL, gtk.RESPONSE_REJECT, gtk.STOCK_OK, gtk.RESPONSE_ACCEPT))
    ff=gtk.FileFilter()
    ff.set_name(_('Shamela BOK files'))
    ff.add_pattern('*.[Bb][Oo][Kk]')
    self.add_dlg.add_filter(ff)
    ff=gtk.FileFilter()
    ff.set_name('All files')
    ff.add_pattern('*')
    self.add_dlg.add_filter(ff)
    self.add_dlg.set_select_multiple(True)
    self.add_dlg.connect('delete-event', lambda w,*a: w.hide() or True)
    self.add_dlg.connect('response', lambda w,*a: w.hide() or True)
    return self.add_dlg.run()

  def rm(self, b):
    l, ls_p = self.lsv.get_selection().get_selected_rows()
    r=map(lambda p: gtk.TreeRowReference(self.ls, p), ls_p)
    for i in r:
      self.ls.remove(self.ls.get_iter(i.get_path()))

  def add_fn(self, fn):
    self.ls.append([fn,os.path.basename(fn),0,-1,"Not started"])

  def add_uri(self, i):
    if i.startswith('file://'): f=unquote(i[7:]); self.add_fn(f)
    else: print "Protocol not supported in [%s]" % i
    
  def drop_data_cb(self, widget, dc, x, y, selection_data, info, t):
    for i in selection_data.get_uris(): self.add_uri(i)
    dc.drop_finish (True, t);


class TabLabel (gtk.HBox):
    """A class for Tab labels"""

    __gsignals__ = {
        "close": (gobject.SIGNAL_RUN_FIRST,
                  gobject.TYPE_NONE,
                  (gobject.TYPE_OBJECT,))
        }

    def __init__ (self, title, child):
        """initialize the tab label"""
        gtk.HBox.__init__(self, False, 4)
        self.title = title
        self.child = child
        self.label = gtk.Label(title)
        self.label.props.max_width_chars = 30
        self.label.set_ellipsize(pango.ELLIPSIZE_MIDDLE)
        self.label.set_alignment(0.0, 0.5)
        # FIXME: use another icon
        icon = gtk.image_new_from_stock(gtk.STOCK_ORIENTATION_PORTRAIT, gtk.ICON_SIZE_MENU)
        close_image = gtk.image_new_from_stock(gtk.STOCK_CLOSE, gtk.ICON_SIZE_MENU)
        close_button = gtk.Button()
        close_button.set_relief(gtk.RELIEF_NONE)
        close_button.connect("clicked", self._close_tab, child)
        close_button.add(close_image)
        self.pack_start(icon, False, False, 0)
        self.pack_start(self.label, True, True, 0)
        self.pack_start(close_button, False, False, 0)

        self.set_data("label", self.label)
        self.set_data("close-button", close_button)
        self.connect("style-set", tab_label_style_set_cb)

    def set_label_text (self, text):
        """sets the text of this label"""
        if text: self.label.set_label(text)

    def _close_tab (self, widget, child):
        self.emit("close", child)

def tab_label_style_set_cb (tab_label, style):
    context = tab_label.get_pango_context()
    metrics = context.get_metrics(tab_label.style.font_desc, context.get_language())
    char_width = metrics.get_approximate_digit_width()
    (width, height) = gtk.icon_size_lookup_for_settings(tab_label.get_settings(), gtk.ICON_SIZE_MENU)
    tab_label.set_size_request(20 * pango.PIXELS(char_width) + 2 * width, -1)
    button = tab_label.get_data("close-button")
    button.set_size_request(width + 4, height + 4)

class ContentPane (gtk.Notebook):
    __gsignals__ = {
        "focus-view-title-changed": (gobject.SIGNAL_RUN_FIRST,
                                     gobject.TYPE_NONE,
                                     (gobject.TYPE_OBJECT, gobject.TYPE_STRING,)),
        "focus-view-load-committed": (gobject.SIGNAL_RUN_FIRST,
                                      gobject.TYPE_NONE,
                                      (gobject.TYPE_OBJECT, gobject.TYPE_OBJECT,)),
        "new-window-requested": (gobject.SIGNAL_RUN_FIRST,
                                 gobject.TYPE_NONE,
                                 (gobject.TYPE_OBJECT,))
        }

    def __init__ (self, default_url, default_title=None, hp=gtk.POLICY_NEVER, vp=gtk.POLICY_ALWAYS):
        """initialize the content pane"""
        gtk.Notebook.__init__(self)
        self.set_scrollable(True)
        self.default_url=default_url
        self.default_title=default_title
        self.hp=hp
        self.vp=vp
        self.props.scrollable = True
        self.props.homogeneous = True
        self.connect("switch-page", self._switch_page)

        self.show_all()
        self._hovered_uri = None

    def load (self, uri):
        """load the given uri in the current web view"""
        child = self.get_nth_page(self.get_current_page())
        wv = child.get_child()
        wv.open(uri)

    def new_tab_with_webview (self, webview):
        """creates a new tab with the given webview as its child"""
        self._construct_tab_view(webview)

    def new_tab (self, url=None):
        """creates a new page in a new tab"""
        # create the tab content
        wv = ThWV()
        self._construct_tab_view(wv, url)
        return wv

    def _construct_tab_view (self, wv, url=None, title=None):
        wv.connect("hovering-over-link", self._hovering_over_link_cb)
        wv.connect("populate-popup", self._populate_page_popup_cb)
        wv.connect("load-committed", self._view_load_committed_cb)
        wv.connect("load-finished", self._view_load_finished_cb)
        wv.connect("create-web-view", self._new_web_view_request_cb)

        # load the content
        self._hovered_uri = None
        if not url: url=self.default_url
        wv.open(url)

        scrolled_window = gtk.ScrolledWindow()
        scrolled_window.props.hscrollbar_policy = self.hp
        scrolled_window.props.vscrollbar_policy = self.vp
        scrolled_window.add(wv)
        scrolled_window.show_all()

        # create the tab
        if not title: title=self.default_title
        if not title: title=url
        label = TabLabel(title, scrolled_window)
        label.connect("close", self._close_tab)
        label.show_all()

        new_tab_number = self.append_page(scrolled_window, label)
        self.set_tab_reorderable(scrolled_window, True)
        self.set_tab_label_packing(scrolled_window, False, False, gtk.PACK_START)
        self.set_tab_label(scrolled_window, label)

        # hide the tab if there's only one
        self.set_show_tabs(self.get_n_pages() > 1)

        self.show_all()
        self.set_current_page(new_tab_number)

    def _populate_page_popup_cb(self, view, menu):
        # misc
        if self._hovered_uri:
            open_in_new_tab = gtk.MenuItem(_("Open Link in New Tab"))
            open_in_new_tab.connect("activate", self._open_in_new_tab, view)
            menu.insert(open_in_new_tab, 0)
            menu.show_all()

    def _open_in_new_tab (self, menuitem, view):
        self.new_tab(self._hovered_uri)

    def _close_tab (self, label, child):
        page_num = self.page_num(child)
        if page_num != -1:
            view = child.get_child()
            view.destroy()
            self.remove_page(page_num)
        self.set_show_tabs(self.get_n_pages() > 1)

    def _switch_page (self, notebook, page, page_num):
        child = self.get_nth_page(page_num)
        view = child.get_child()
        frame = view.get_main_frame()
        self.emit("focus-view-load-committed", view, frame)

    def _hovering_over_link_cb (self, view, title, uri):
        self._hovered_uri = uri

    def _view_load_committed_cb (self, view, frame):
        self.emit("focus-view-load-committed", view, frame)

    def _view_load_finished_cb(self, view, frame):
        child = self.get_nth_page(self.get_current_page())
        label = self.get_tab_label(child)
        title = frame.get_title()
        if not title:
           title = frame.get_uri()
        label.set_label_text(title)

    def _new_web_view_request_cb (self, web_view, web_frame):
        view=self.new_tab()
        view.connect("web-view-ready", self._new_web_view_ready_cb)
        return view

    def _new_web_view_ready_cb (self, web_view):
        self.emit("new-window-requested", web_view)

class ThIndexerWindow(gtk.Window):
  def __init__(self, main):
    gtk.Window.__init__(self)
    self.main=main
    self.connect('delete-event', lambda w,*a: w.hide() or True)
    self.set_title(_('Manage search index'))
    self.set_type_hint(gtk.gdk.WINDOW_TYPE_HINT_DIALOG)
    vb=gtk.VBox(False,2); self.add(vb)
    hb=gtk.HBox(False,2); vb.pack_start(hb, False, False, 0)
    self.progress=gtk.ProgressBar()
    b=gtk.Button(_("Queue new books"))
    b.connect('clicked', self.indexNew)
    hb.pack_start(b, False, False, 0)
    hb.pack_start(self.progress, False, False, 0)
    hb.pack_start(gtk.Button(stock=gtk.STOCK_CANCEL), False, False, 0)
    self.update()
    glib.timeout_add(250, self.update)


  def indexNew(self, *a):
    self.main.th.asyncIndexer.queueIndexNew()
    if not self.main.th.asyncIndexer.started: self.main.th.asyncIndexer.start()
    self.update()

  def update(self, *a):
    if not self.get_visible(): return True
    j=self.main.th.asyncIndexer.jobs()
    if j>0:
      self.progress.set_text (_("Indexing ... (%d left)") % j)
      self.progress.pulse()
    else:
      self.progress.set_text (_("no indexing jobs left"))
    return True


class ThMainWindow(gtk.Window):
  def __init__(self, th, port, server):
    self.th = th
    self.port = port
    self.server = server # we need this to quit the server when closing main window
    gtk.window_set_default_icon_name('thawab')
    gtk.Window.__init__(self)
    self.set_title(_('Thawab'))
    self.set_default_size(600, 480)
    
    self.import_w=None
    self.ix_w=ThIndexerWindow(self)
    
    vb=gtk.VBox(False,0); self.add(vb)

    tools=gtk.Toolbar()
    vb.pack_start(tools, False, False, 2)

    b=gtk.ToolButton(gtk.STOCK_NEW)
    b.connect('clicked', lambda bb: self._content.new_tab())
    b.set_tooltip_text(_("Open a new tab"))
    tools.insert(b, -1)
    
    # TODO: add navigation buttons (back, forward ..etc.) and zoom buttons

    img=gtk.Image()
    img.set_from_stock(gtk.STOCK_CONVERT, gtk.ICON_SIZE_BUTTON)
    b=gtk.ToolButton(icon_widget=img, label=_("Import"))
    b.set_tooltip_text(_("Import .bok files"))
    b.connect('clicked', self.import_cb)
    tools.insert(b, -1)

    img=gtk.Image()
    img.set_from_stock(gtk.STOCK_FIND_AND_REPLACE, gtk.ICON_SIZE_BUTTON)
    b=gtk.ToolButton(icon_widget=img, label=_("Index"))
    b.set_is_important(True)
    b.set_tooltip_text(_("Create search index"))
    b.connect('clicked', lambda *a: self.ix_w.show_all())
    tools.insert(b, -1)

    img=gtk.Image()
    img.set_from_stock(gtk.STOCK_PREFERENCES, gtk.ICON_SIZE_BUTTON)
    b=gtk.ToolButton(icon_widget=img, label=_("Fixes"))
    b.set_is_important(True)
    b.set_tooltip_text(_("Misc Fixes"))
    #b.connect('clicked', self.import_cb)
    tools.insert(b, -1)
    
    
    self._content= ContentPane("http://127.0.0.1:%d/" % port, _("Thawab"))
    vb.pack_start(self._content,True, True, 2)
    self._content.new_tab()

    self.connect("delete_event", self.quit)
    self.drag_dest_set(gtk.DEST_DEFAULT_ALL,targets_l,(1<<5)-1)
    self.connect('drag-data-received', self.drop_data_cb)
    
    self.show_all()

  def drop_data_cb(self, widget, dc, x, y, selection_data, info, t):
    if not self.import_w: self.import_w=ThImportWindow(self)
    for i in selection_data.get_uris():
      self.import_w.add_uri(i)
    self.import_w.show()
    dc.drop_finish (True, t);


  def import_cb(self, b):
    if not self.import_w: self.import_w=ThImportWindow(self)
    self.import_w.show()

  def quit(self,*args):
    self.server.running=False
    gtk.main_quit()
    return False

THAWAB_HIGH_PORT=18080

def launchServer():
  exedir=os.path.dirname(sys.argv[0])
  datadir=os.path.join(exedir,'thawab-files')
  if not os.path.exists(datadir):
    datadir=os.path.join(exedir,'..','share','thawab','thawab-files')
  th=Thawab.core.ThawabMan(os.path.expanduser('~/.thawab'), isMonolithic=False)
  app=webApp(
    th,True, 
    os.path.join(datadir,'templates'),
    staticBaseDir={'/_files/':os.path.join(datadir,'media')})
  launched=False
  port=THAWAB_HIGH_PORT
  while(not launched):
    try: server=httpserver.serve(app, host='127.0.0.1', port=port, start_loop=False)
    except socket.error: port+=1
    else: launched=True
  return th, port, server

def main():
  exedir=os.path.dirname(sys.argv[0])
  ld=os.path.join(exedir, 'locale')
  if not os.path.exists(ld): ld=os.path.join(exedir,'..','share','locale')
  gettext.install('thawab', ld, unicode=0)
  th, port, server=launchServer()

  threading.Thread(target=server.serve_forever, args=()).start()
  while(not server.running): time.sleep(0.25)
  gtk.gdk.threads_init()
  #gtk.gdk.threads_enter()
  w=ThMainWindow(th, port,server)
  #gtk.gdk.threads_leave()
  gtk.main()

if __name__ == "__main__":
  main()
