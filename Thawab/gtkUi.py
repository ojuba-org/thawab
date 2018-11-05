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
import gi
gi.require_version("Gtk", "3.0")
gi.require_version("WebKit2", "4.0")
from gi.repository import Gtk, Gdk, GObject, WebKit2, Pango, GLib, Gio
from subprocess import Popen, PIPE
from urllib import unquote

import Thawab.core

from Thawab.webApp import webApp, get_theme_dirs
from Thawab.shamelaUtils import ShamelaSqlite, shamelaImport
from Thawab.platform import uri_to_filename
from paste import httpserver

setsid = getattr(os, 'setsid', None)
if not setsid: setsid = getattr(os, 'setpgrp', None)
_ps = []

def run_in_bg(cmd):
    global _ps
    setsid = getattr(os, 'setsid', None)
    if not setsid: setsid = getattr(os, 'setpgrp', None)
    _ps = filter(lambda x: x.poll() != None,_ps) # remove terminated processes from _ps list
    _ps.append(Popen(cmd,0,'/bin/sh',shell = True, preexec_fn = setsid))

def get_exec_full_path(fn):
    a = filter(lambda p: os.access(p, os.X_OK),
               map(lambda p: os.path.join(p, fn),
                    os.environ['PATH'].split(os.pathsep)))
    if a:
        return a[0]
    return None

def guess_browser():
    e = get_exec_full_path("xdg-open")
    if not e:
        e = get_exec_full_path("firefox")
    if not e:
        e = "start"
    return e

broswer = guess_browser()

def sure(msg, parent = None):
    dlg = Gtk.MessageDialog(parent,
                            Gtk.DialogFlags.MODAL,
                            Gtk.MessageType.QUESTION,
                            Gtk.ButtonsType.YES_NO,
                            msg)
    dlg.connect("response", lambda *args: dlg.hide())
    r = dlg.run()
    dlg.destroy()
    return r == Gtk.ResponseType.YES

def info(msg, parent = None):
    dlg = Gtk.MessageDialog(parent,
                            Gtk.DialogFlags.MODAL,
                            Gtk.MessageType.INFO,
                            Gtk.ButtonsType.OK,
                            msg)
    dlg.connect("response", lambda *args: dlg.hide())
    r = dlg.run()
    dlg.destroy()

def error(msg, parent = None):
    dlg = Gtk.MessageDialog(parent,
                            Gtk.DialogFlags.MODAL,
                            Gtk.MessageType.ERROR,
                            Gtk.ButtonsType.OK,
                            msg)
    dlg.connect("response", lambda *args: dlg.hide())
    r = dlg.run()
    dlg.destroy()

class ThWV(WebKit2.WebView):
    def __init__(self):
        WebKit2.WebView.__init__(self)
        #self.set_full_content_zoom(True)
        #self.connect_after("populate-popup", self.populate_popup)
        #self.connect("navigation-requested", self._navigation_requested_cb)
        
        #self.connect_after("context-menu", self.populate_popup)
        self.connect("create", self._navigation_requested_cb)

    """def _navigation_requested_cb(self, view, frame, networkRequest):
        uri = networkRequest.get_uri()
        if not uri.startswith('http://127.0.0.1') and not uri.startswith('http://localhost'):
            run_in_bg("%s '%s'" % (broswer ,uri))
            return 1
        return 0"""
        
    def _navigation_requested_cb(self, web_view, navigation_action):
        networkRequest = navigation_action.get_request()
        uri = networkRequest.get_uri()
        if not uri.startswith('http://127.0.0.1') and not uri.startswith('http://localhost'):
            run_in_bg("%s '%s'" % (broswer ,uri))
            return 1
        return 0

    """def reload_if_index(self, *a, **kw):
        if self.get_property('uri').endswith('/index/'):
            self.reload()"""
            
    def reload_if_index(self, *a, **kw):
        uri = self.props.uri
        if uri.endswith('/index/'):
            self.reload()

    """def _eval_js(self, e):
         \"""
         can be used to eval a javascript expression
         eg. to obtain value of a javascript variable given its name
         \"""
         self.execute_script('thawab_eval_js_oldtitle=document.title;document.title=%s;' % e)
         r = self.get_main_frame().get_title()
         self.execute_script('document.title=thawab_eval_js_oldtitle;')
         return r"""
         
    def _eval_js(self, e):
         """
         can be used to eval a javascript expression
         eg. to obtain value of a javascript variable given its name
         """
         self.run_javascript('thawab_eval_js_oldtitle=document.title;document.title=%s;' % e,None,None,None)
         r = self.props.title
         self.run_javascript('document.title=thawab_eval_js_oldtitle;',None,None,None)
         return r

    """def populate_popup(self, view, menu):
        menu.append(Gtk.SeparatorMenuItem.new())
        i = Gtk.ImageMenuItem.new_from_stock(Gtk.STOCK_ZOOM_IN, None)
        i.connect('activate', lambda m,v,*a,**k: v.zoom_in(), view)
        menu.append(i)
        i = Gtk.ImageMenuItem.new_from_stock(Gtk.STOCK_ZOOM_OUT, None)
        i.connect('activate', lambda m,v,**k: v.zoom_out(), view)
        menu.append(i)
        i = Gtk.ImageMenuItem.new_from_stock(Gtk.STOCK_ZOOM_100, None)
        i.connect('activate', lambda m,v,*a,**k: v.get_zoom_level() == 1.0 or v.set_zoom_level(1.0), view)
        menu.append(i)

        menu.show_all()
        return False"""
        
    """def populate_popup(self, view, menu, event, hit_test_result):
        m = Gtk.SeparatorMenuItem()
        m = WebKit2.ContextMenuItem.new_separator()
        print(menu)
        print(m)
        menu.append(m)
        
        
        i = WebKit2.ContextMenuItem.new_from_stock_action(WebKit2.ContextMenuAction.GO_FORWARD)
        print(i)
        i.connect('activate', lambda m,v,*a,**k: v.zoom_in(), view)
        menu.append(i)
        i = WebKit2.ContextMenuItem.new_from_stock_action(WebKit2.ContextMenuAction.GO_BACK)
        i.connect('activate', lambda m,v,**k: v.zoom_out(), view)
        menu.append(i)
        i = WebKit2.ContextMenuItem.new_from_stock_action(WebKit2.ContextMenuAction.RELOAD)
        i.connect('activate', lambda m,v,*a,**k: v.get_zoom_level() == 1.0 or v.set_zoom_level(1.0), view)
        menu.append(i)

        self.show_all()
        return False"""
        
        
    def zoom_in(self,*a,**kw):##########new
        if self.get_zoom_level()==3:
            return
        self.set_zoom_level(self.get_zoom_level()+0.1)
        
    def zoom_out(self,*a,**kw):##########new
        if self.get_zoom_level()==1:
            return
        self.set_zoom_level(self.get_zoom_level()-0.1)

targets = Gtk.TargetList.new([])
targets.add_uri_targets((1 << 5) -1)
class ThImportWindow(Gtk.Window):
    def __init__(self, main):
        Gtk.Window.__init__(self)
        self.progress_dict = { }
        self.progress_phase = 0
        self.progress_books_in_file = 0
        self.progress_element = 0
        self.add_dlg = None
        self.set_size_request(-1, 400)
        ## prepare dnd 
        self.drag_dest_set(Gtk.DestDefaults.ALL, [], Gdk.DragAction.COPY)
        self.drag_dest_set_target_list(targets)
        self.connect('drag-data-received', self.drop_data_cb)
        self.set_title(_('Import Shamela .bok files'))
        self.set_type_hint(Gdk.WindowTypeHint.DIALOG)
        self.set_modal(True)
        self.set_transient_for(main)
        self.main = main
        self.connect('delete-event', self.close_cb)
        self.connect('destroy', self.close_cb)
        vb = Gtk.VBox(False,2)
        self.add(vb)
        hb0 = Gtk.HBox(False,2)
        vb.pack_start(hb0,False, False, 2)
        self.tool = hb = Gtk.HBox(False,2)
        hb0.pack_start(hb,False, False, 2)
        b = Gtk.Button(stock = Gtk.STOCK_ADD)
        b.connect('clicked', self.add_cb, self)
        hb.pack_start(b, False, False, 2)
        b = Gtk.Button(stock = Gtk.STOCK_REMOVE)
        b.connect('clicked', self.rm)
        hb.pack_start(b, False, False, 2)
        b = Gtk.Button(stock = Gtk.STOCK_CLEAR)
        b.connect('clicked', lambda *a: self.ls.clear())
        hb.pack_start(b, False, False, 2)
        b = Gtk.Button(stock = Gtk.STOCK_CONVERT)
        b.connect('clicked', self.start)
        hb.pack_start(b, False, False, 2)
        self.progress = Gtk.ProgressBar()
        self.progress.set_fraction(0.0)
        hb0.pack_start(self.progress, True, True, 2)
        self.cancel_b = b = Gtk.Button(stock = Gtk.STOCK_CANCEL)
        b.connect('clicked', self.stop)
        b.set_sensitive(False)
        hb0.pack_start(b, False, False, 2)
        
        self.close_b = b = Gtk.Button(stock = Gtk.STOCK_CLOSE)
        b.connect('clicked', self.close_cb)
        hb0.pack_start(b, False, False, 2)
        
        self.ls = Gtk.ListStore(str,str,float,int,str) # fn, basename, percent, pulse, label
        self.lsv = Gtk.TreeView(self.ls)
        #self.lsv.set_size_request(250, -1)
        cells = []
        cols = []
        cells.append(Gtk.CellRendererText())
        cols.append(Gtk.TreeViewColumn('Files', cells[-1], text = 1))
        cols[-1].set_sizing(Gtk.TreeViewColumnSizing.AUTOSIZE)
        cols[-1].set_resizable(True)
        cols[-1].set_expand(True)
        cells.append(Gtk.CellRendererProgress())
        cols.append(Gtk.TreeViewColumn('%', cells[-1], value = 2,pulse = 3,text = 4))
        cols[-1].set_expand(False)
        self.lsv.set_headers_visible(True)
        self.lsv.get_selection().set_mode(Gtk.SelectionMode.MULTIPLE)

        for i in cols:
            self.lsv.insert_column(i, -1)

        scroll = Gtk.ScrolledWindow()
        scroll.set_policy(Gtk.PolicyType.NEVER,Gtk.PolicyType.AUTOMATIC)
        scroll.add(self.lsv)
        vb.pack_start(scroll,True, True, 2)

        
        self.x = x = Gtk.Expander.new(_("Advanced options"))
        vb.pack_start(x, False, False, 2)

        xvb = Gtk.VBox(False,2); x.add(xvb)

        f = Gtk.Frame.new(_('Performance tuning:'))
        xvb.add(f)
        fvb = Gtk.VBox(False,2)
        f.add(fvb)
        hb = Gtk.HBox(False,2)
        fvb.add(hb)

        self.in_mem = Gtk.CheckButton(_('in memory'))
        self.in_mem.set_tooltip_text(_("faster but consumes more memory and harder to debug."))
        hb.pack_start(self.in_mem, False, False, 2)


        f = Gtk.Frame.new('Version Control:')
        xvb.add(f)
        fvb = Gtk.VBox(False,2); f.add(fvb)
        hb = Gtk.HBox(False,2); fvb.add(hb)

        hb.pack_start(Gtk.Label(_('Release Major:')), False, False, 2)
        adj = Gtk.Adjustment(0, 0, 10000, 1, 10, 0)
        self.releaseMajor = s = Gtk.SpinButton()
        s.set_adjustment(adj)
        hb.pack_start(self.releaseMajor, False, False, 2)
        hb.pack_start(Gtk.Label(_('Release Minor:')), False, False, 2)
        self.releaseMinor = s = Gtk.SpinButton()
        s.set_adjustment(adj)
        hb.pack_start(self.releaseMinor, False, False, 2)

        f = Gtk.Frame.new('Footnotes:'); xvb.add(f)
        fvb = Gtk.VBox(False,2); f.add(fvb)
        hb = Gtk.HBox(False,2); fvb.add(hb)

        hb.pack_start(Gtk.Label(_('Prefix:')), False, False, 2)
        self.ft_prefix = Gtk.Entry()
        self.ft_prefix.set_text('(')
        self.ft_prefix.set_width_chars(3)
        hb.pack_start(self.ft_prefix, False, False, 2)

        hb.pack_start(Gtk.Label(_('Suffix:')), False, False, 2)
        self.ft_suffix = Gtk.Entry()
        self.ft_suffix.set_text(')')
        self.ft_suffix.set_width_chars(3)
        hb.pack_start(self.ft_suffix, False, False, 2)

        self.ft_at_line_start = Gtk.CheckButton(_('only at line start'))
        hb.pack_start(self.ft_at_line_start, False, False, 2)

        hb = Gtk.HBox(False,2); fvb.add(hb)
        hb.pack_start(Gtk.Label(_('in between spaces:')), False, False, 2)
        self.ft_sp = [Gtk.RadioButton(group = None, label = _('no spaces'))]
        self.ft_sp.append(Gtk.RadioButton(group=self.ft_sp[0], label = _('optional white-space')))
        self.ft_sp.append(Gtk.RadioButton(group=self.ft_sp[0], label = _('optional white-spaces')))
        for i in self.ft_sp: hb.pack_start(i, False, False, 2)

        f = Gtk.Frame.new('Footnote anchors in body:'); xvb.add(f)
        fvb = Gtk.VBox(False,2); f.add(fvb)
        hb = Gtk.HBox(False,2); fvb.add(hb)

        hb.pack_start(Gtk.Label(_('Prefix:')), False, False, 2)
        self.bft_prefix = Gtk.Entry()
        self.bft_prefix.set_text('(')
        self.bft_prefix.set_width_chars(3)
        hb.pack_start(self.bft_prefix, False, False, 2)

        hb.pack_start(Gtk.Label(_('Suffix:')), False, False, 2)
        self.bft_suffix = Gtk.Entry()
        self.bft_suffix.set_text(')')
        self.bft_suffix.set_width_chars(3)
        hb.pack_start(self.bft_suffix, False, False, 2)

        hb = Gtk.HBox(False,2); fvb.add(hb)
        hb.pack_start(Gtk.Label(_('in between spaces:')), False, False, 2)
        self.bft_sp = [Gtk.RadioButton(group = None, label = _('no spaces'))]
        self.bft_sp.append(Gtk.RadioButton(group=self.bft_sp[0], label = _('optional white-space')))
        self.bft_sp.append(Gtk.RadioButton(group=self.bft_sp[0], label = _('optional white-spaces')))
        for i in self.bft_sp: hb.pack_start(i, False, False, 2)

        # TODO: add options to specify version and revision
        # TODO: add options to specify wither to break by hno
        # TODO: add options for handling existing files (overwrite?)

        ft_at_line_start = False
        ft_prefix = u'('
        ft_suffix = u')'
        ft_sp = u'' # can be ur'\s?' or ur'\s*'
        body_footnote_re = re.escape(ft_prefix)+ft_sp+ur'(\d+)'+ft_sp+re.escape(ft_suffix)
        footnote_re = (ft_at_line_start and u'^\s*' or u'') + body_footnote_re
        ft_prefix_len = len(ft_prefix)
        ft_suffix_len = len(ft_suffix)
        #shamelaImport(cursor, sh, bkid, footnote_re = ur'\((\d+)\)', body_footnote_re = ur'\((\d+)\)', ft_prefix_len = 1, ft_suffix_len = 1):
        #self.show_all()

    def close_cb(self, *w):
        return self.hide() or True
        
    def element_pulse_cb(self, i):
        self.ls[(i,)][2] = 0
        self.ls[(i,)][3] = int(abs(self.ls[(i,)][3])+1)
        Gtk.main_iteration()

    def element_progress_cb(self, i, percent, text = None):
        l = self.ls[(i,)]
        if percent >= 0.0:
            l[2] = percent
        if text != None and not 'working' in text:
            l[4] = text
        else:
            l[4] = '%s%%' % str(int(percent))
        Gtk.main_iteration()

    def progress_cb(self, msg, p, *d, **kw):
        # print " ** progress phase %d: [%g%% completed] %s" % (self.progress_phase, p, msg)
        i = self.progress_element
        N = len(self.ls)
        j = self.progress_book_in_file
        n = self.progress_books_in_file
        if n == 0 or N == 0:
            return
        if self.progress_phase == 1:
            percent = p*0.25
        else:
            percent = (75.0/n)*j + p*0.75/n + 25.0
        
        if not kw.has_key('show_msg'):
            msg = _("working ...")
        self.element_progress_cb(i, percent, msg)
        self.progress.set_fraction( float(i)/N + percent/100.0/N )
        Gtk.main_iteration()

    def start_cb(self):
        self.tool.set_sensitive(False)
        self.x.set_sensitive(False)
        self.cancel_b.set_sensitive(True)
        self.progress_dict['cancel'] = False

    def start(self, b):
        self.start_cb()
        self.progress.set_text(_("working ..."))
        ft_at_line_start = self.ft_at_line_start.get_active()
        ft_prefix = self.ft_prefix.get_text()
        ft_prefix_len = len(ft_prefix)
        
        ft_suffix=self.ft_suffix.get_text()
        ft_suffix_len = len(ft_suffix)
        
        ft_sp = [u'', ur'\s?' , ur'\s*'][ [i.get_active() for i in self.ft_sp].index(True) ]
        footnote_re = (ft_at_line_start and u'^\s*' or u'') + \
                      re.escape(ft_prefix) + \
                      ft_sp+ur'(\d+)' + \
                      ft_sp + \
                      re.escape(ft_suffix)

        bft_prefix=self.bft_prefix.get_text()
        bft_suffix=self.bft_suffix.get_text()
        bft_sp = [u'', ur'\s?' , ur'\s*'][ [i.get_active() for i in self.bft_sp].index(True) ]
        body_footnote_re = re.escape(bft_prefix) + \
                           bft_sp + \
                           ur'(\d+)' + \
                           bft_sp + \
                           re.escape(bft_suffix)

        if not self.in_mem.get_active():
            fh, db_fn = tempfile.mkstemp(suffix = '.sqlite', prefix = 'th_shamela_tmp')
        else:
            db_fn = None
        for i,l in enumerate(self.ls):
            self.progress_element = i
            self.progress_book_in_file = 0
            self.progress_books_in_file = 1
            fn = l[0]
            if db_fn:
                f = open(db_fn, "w")
                f.truncate(0)
                f.close()
                cn = sqlite3.connect(db_fn, isolation_level = None)
            else:
                cn = None
            self.progress_phase = 1
            try:
                sh = ShamelaSqlite(fn,
                               cn,
                               int(self.releaseMajor.get_value()),
                               int(self.releaseMinor.get_value()),
                               self.progress_cb,
                               progress_dict = self.progress_dict)
            except TypeError:
                print "not a shamela file"
                continue
            except OSError:
                print "mdbtools is not installed"
                break
            if not sh.toSqlite():
                # canceled
                self.progress.set_text(_("Canceled"))
                self.element_progress_cb(self.progress_element, -1.0, _("Canceled"))
                return
            self.progress_phase = 2
            ids = sh.getBookIds()
            self.progress_books_in_file = len(ids)
            for j, bkid in enumerate(ids):
                self.progress_book_in_file = j
                ki = self.main.th.mktemp()
                c = ki.seek(-1,-1)
                m = shamelaImport(c,
                                  sh,
                                  bkid,
                                  footnote_re,
                                  body_footnote_re,
                                  ft_prefix_len,
                                  ft_suffix_len)
                if m == None:
                    # canceled
                    self.progress.set_text(_("Canceled"))
                    self.element_progress_cb(self.progress_element, -1.0, _("Canceled"))
                    return
                c.flush()
                t_fn = os.path.join(self.main.th.prefixes[0],
                                    'db',
                                    u"".join((m['kitab'] + \
                                              u"-" + \
                                              m['version'] + \
                                              Thawab.core.th_ext,)))
                #print "moving %s to %s" % (ki.uri, t_fn)
                try:
                    shutil.move(ki.uri, t_fn)
                except OSError:
                    print "unable to move converted file." # windows can't move an opened file
                # FIXME: close ki in a clean way so the above code works in windows
            self.progress_cb(_("Done"), 100.0, show_msg = True)

        if db_fn and os.path.exists(db_fn):
            try:
                os.unlink(db_fn)
            except OSError:
                pass
        #self.element_progress_cb(0, 25.0, "testing")
        self.tool.set_sensitive(True)
        self.x.set_sensitive(True)
        self.cancel_b.set_sensitive(False)
        self.main.th.loadMeta()
        self.main._do_in_all_views('reload_if_index')
        self.progress.set_text(_("Done"))
        info(_("Convert Book, Done"), self.main)
        self.ls.clear()
        self.progress.set_text("")
        self.progress.set_fraction(0.0)
        self.hide()

    def stop(self, b):
        self.tool.set_sensitive(True)
        self.x.set_sensitive(True)
        self.cancel_b.set_sensitive(False)
        self.progress_dict['cancel'] = True

    def add_cb(self, b, parent=None):
        if self.run_add_dlg(parent) == Gtk.ResponseType.ACCEPT:
            for i in self.add_dlg.get_filenames():
                self.add_fn(i)

    def run_add_dlg(self, parent=None):
        if self.add_dlg:
            return self.add_dlg.run()
        self.add_dlg = Gtk.FileChooserDialog(_("Select files to import"),
                                             parent = parent,
                                             buttons=(Gtk.STOCK_CANCEL,
                                             Gtk.ResponseType.REJECT,
                                             Gtk.STOCK_OK,
                                             Gtk.ResponseType.ACCEPT))
        ff = Gtk.FileFilter()
        ff.set_name(_('Shamela BOK files'))
        ff.add_pattern('*.[Bb][Oo][Kk]')
        self.add_dlg.add_filter(ff)
        ff = Gtk.FileFilter()
        ff.set_name('All files')
        ff.add_pattern('*')
        self.add_dlg.add_filter(ff)
        self.add_dlg.set_select_multiple(True)
        self.add_dlg.connect('delete-event', lambda w,*a: w.hide() or True)
        self.add_dlg.connect('response', lambda w,*a: w.hide() or True)
        return self.add_dlg.run()

    def rm(self, b):
        l, ls_p = self.lsv.get_selection().get_selected_rows()
        r = map(lambda p: Gtk.TreeRowReference.new(self.ls, p), ls_p)
        for i in r:
            self.ls.remove(self.ls.get_iter(i.get_path()))

    def add_fn(self, fn):
        self.ls.append([fn, os.path.basename(fn), float(0), -1, "Not started"])

    def add_uri(self, i):
        if i.startswith('file://'):
            f = uri_to_filename(unquote(i[7:]))
            self.add_fn(f)
        else:
            print "Protocol not supported in [%s]" % i
        
    def drop_data_cb(self, widget, dc, x, y, selection_data, info, t):
        for i in selection_data.get_uris():
            self.add_uri(i)
        #dc.drop_finish(True, t)


class TabLabel(Gtk.HBox):
    """A class for Tab labels"""

    __gsignals__ = {
        "close": (GObject.SIGNAL_RUN_FIRST,
                  GObject.TYPE_NONE,
                  (GObject.TYPE_OBJECT,))
        }

    def __init__ (self, title, child):
        """initialize the tab label"""
        Gtk.HBox.__init__(self, False, 4)
        self.title = title
        self.child = child
        self.label = Gtk.Label(title)
        self.label.props.max_width_chars = 30
        self.label.set_ellipsize(Pango.EllipsizeMode.MIDDLE)
        self.label.set_alignment(0.0, 0.5)
        # FIXME: use another icon
        icon = Gtk.Image.new_from_icon_name("thawab", Gtk.IconSize.MENU)
        close_image = Gtk.Image.new_from_stock(Gtk.STOCK_CLOSE, Gtk.IconSize.MENU)
        close_button = Gtk.Button()
        close_button.set_relief(Gtk.ReliefStyle.NONE)
        close_button.connect("clicked", self._close_tab, child)
        close_button.add(close_image)
        self.pack_start(icon, False, False, 0)
        self.pack_start(self.label, True, True, 0)
        self.pack_start(close_button, False, False, 0)

        #self.set_data("label", self.label)
        #self.set_data("close-button", close_button)
        self.connect("style-set", tab_label_style_set_cb)

    def set_label_text (self, text):
        """sets the text of this label"""
        if text:
            self.label.set_label(text)

    def _close_tab (self, widget, child):
        self.emit("close", child)

def tab_label_style_set_cb (tab_label, style):
    #context = tab_label.get_pango_context()
    #font_desc = Pango.font_description_from_string(tab_label.label.get_label())
    #metrics = context.get_metrics(font_desc, context.get_language())
    #metrics = context.get_metrics(tab_label.style.font_desc, context.get_language())
    #char_width = metrics.get_approximate_digit_width()
    #(icons, width, height) = Gtk.icon_size_lookup_for_settings(tab_label.get_settings(),
    #                                                           Gtk.IconSize.MENU)
    #tab_label.set_size_request(20 * char_width + 2 * width, -1)
    tab_label.set_size_request(230, -1)
    #button = tab_label.get_data("close-button")
    #button.set_size_request(width + 4, height + 4)

class ContentPane (Gtk.Notebook):
    __gsignals__ = {
        "focus-view-title-changed": (GObject.SIGNAL_RUN_FIRST,
                                     GObject.TYPE_NONE,
                                     (GObject.TYPE_OBJECT,
                                      GObject.TYPE_STRING,)),
        "focus-view-load-committed": (GObject.SIGNAL_RUN_FIRST,
                                      GObject.TYPE_NONE,
                                      (GObject.TYPE_OBJECT,
                                       GObject.TYPE_OBJECT,)),
        "new-window-requested": (GObject.SIGNAL_RUN_FIRST,
                                 GObject.TYPE_NONE,
                                 (GObject.TYPE_OBJECT,))
        }

    def __init__ (self, default_url = None,
                        default_title = None,
                        hp = Gtk.PolicyType.NEVER,
                        vp = Gtk.PolicyType.ALWAYS):
        """initialize the content pane"""
        Gtk.Notebook.__init__(self)
        self.set_scrollable(True)
        self.default_url = default_url
        self.default_title = default_title
        self.hp = hp
        self.vp = vp
        self.props.scrollable = True
        #self.props.homogeneous = True
        self.connect("switch-page", self._switch_page)

        self.show_all()
        self._hovered_uri = None

    """def load (self, uri):
        \"""load the given uri in the current web view\"""
        child = self.get_nth_page(self.get_current_page())
        wv = child.get_child()
        #wv.open(uri)
        wv.load_uri(uri)"""
        
    def new_tab_with_webview (self, webview):
        """creates a new tab with the given webview as its child"""
        self._construct_tab_view(webview)

    def new_tab (self, url = None):
        """creates a new page in a new tab"""
        # create the tab content
        wv = ThWV()
        self._construct_tab_view(wv, url)
        return wv

    """def _construct_tab_view (self, wv, url = None, title = None):
        wv.connect("hovering-over-link", self._hovering_over_link_cb)
        wv.connect("populate-popup", self._populate_page_popup_cb)
        wv.connect("load-committed", self._view_load_committed_cb)
        wv.connect("load-finished", self._view_load_finished_cb)
        wv.connect("create-web-view", self._new_web_view_request_cb)

        # load the content
        self._hovered_uri = None
        if not url:
            url=self.default_url
        if url:
            wv.open(url)

        scrolled_window = Gtk.ScrolledWindow()
        scrolled_window.props.hscrollbar_policy = self.hp
        scrolled_window.props.vscrollbar_policy = self.vp
        scrolled_window.add(wv)
        scrolled_window.show_all()

        # create the tab
        if not title: title=self.default_title
        if not title: title = url
        label = TabLabel(title, scrolled_window)
        label.connect("close", self._close_tab)
        label.show_all()

        new_tab_number = self.append_page(scrolled_window, label)
        self.set_tab_reorderable(scrolled_window, True)
        #self.set_tab_label_packing(scrolled_window, False, False, Gtk.PACK_START)
        self.set_tab_label(scrolled_window, label)

        # hide the tab if there's only one
        self.set_show_tabs(self.get_n_pages() > 1)
        self.show_all()
        self.set_current_page(new_tab_number)"""
        
    def _construct_tab_view (self, wv, url = None, title = None):
        wv.connect("mouse-target-changed", self._hovering_over_link_cb)
        #wv.connect("context-menu", self._populate_page_popup_cb)
        wv.connect("load_changed", self._view_load_committed_cb)
        wv.connect("load_changed", self._view_load_finished_cb)
        wv.connect("create", self._new_web_view_request_cb)

        # load the content
        if not self._hovered_uri :
            if not url:
                url=self.default_url
            if url:
                wv.load_uri(url)
        else:
            wv.load_uri(self._hovered_uri)
            self._hovered_uri= None
        
        scrolled_window = Gtk.ScrolledWindow()
        scrolled_window.props.hscrollbar_policy = self.hp
        scrolled_window.props.vscrollbar_policy = self.vp
        scrolled_window.add(wv)
        scrolled_window.show_all()
        
        # create the tab
        if not title: title=self.default_title
        if not title: title = url
        label = TabLabel(title, scrolled_window)
        label.connect("close", self._close_tab)
        label.show_all()

        new_tab_number = self.append_page(scrolled_window, label)
        self.set_tab_reorderable(scrolled_window, True)
        #self.set_tab_label_packing(scrolled_window, False, False, Gtk.PACK_START)
        self.set_tab_label(scrolled_window, label)

        # hide the tab if there's only one
        self.set_show_tabs(self.get_n_pages() > 1)
        self.show_all()
        self.set_current_page(new_tab_number)
        
    """def _populate_page_popup_cb(self, view, menu):
        # misc
        if self._hovered_uri:
            open_in_new_tab = Gtk.MenuItem(_("Open Link in New Tab"))
            open_in_new_tab.connect("activate", self._open_in_new_tab, view)
            menu.insert(open_in_new_tab, 0)
            menu.show_all()"""
            
    """def _populate_page_popup_cb(self, view, menu, event, hit_test_result):
        # misc
        if self._hovered_uri:
            open_in_new_tab = WebKit2.ContextMenuItem.new_from_stock_action_with_label(WebKit2.ContextMenuAction.OPEN_LINK_IN_NEW_WINDOW ,_("Open Link in New Tab"))
            #open_in_new_tab.connect("activate", self._open_in_new_tab, view)
            menu.insert(open_in_new_tab, 0)
            #menu.show_all()"""

    def _open_in_new_tab (self, menuitem, view):
        self.new_tab(self._hovered_uri)

    def _close_tab (self, label, child):
        page_num = self.page_num(child)
        if page_num  !=  -1:
            view = child.get_child()
            view.destroy()
            self.remove_page(page_num)
        self.set_show_tabs(self.get_n_pages() > 1)

    """def _switch_page (self, notebook, page, page_num):
        child = self.get_nth_page(page_num)
        view = child.get_child()
        frame = view.get_main_frame()
        self.emit("focus-view-load-committed", view, frame)"""
    
    def _switch_page (self, notebook, page, page_num):
        child = self.get_nth_page(page_num)
        viewport = child.get_child()
        web_view = viewport.get_child()
        self.emit("focus-view-load-committed", viewport, web_view)

    """def _hovering_over_link_cb (self, view, title, uri):
        self._hovered_uri = uri"""

    def _hovering_over_link_cb (self,web_view, hit_test_result, modifiers):
        if hit_test_result.context_is_link():
            self._hovered_uri = hit_test_result.get_link_uri()

    """def _view_load_committed_cb (self, view, frame):
        self.emit("focus-view-load-committed", view, frame)"""

    def _view_load_committed_cb (self, web_view, load_event):
        if load_event==2: #WebKit2.LoadEvent.COMMITTED
            viewport = web_view.get_parent()
            self.emit("focus-view-load-committed", viewport, web_view)
            
    """def _view_load_finished_cb(self, view, frame):
        child = self.get_nth_page(self.get_current_page())
        label = self.get_tab_label(child)
        title = frame.get_title()
        if not title:
             title = frame.get_uri()
        label.set_label_text(title)"""
        
    def _view_load_finished_cb(self, web_view, load_event):
        if load_event==3: #WebKit2.LoadEvent.FINISHED 
            child = self.get_nth_page(self.get_current_page())
            label = self.get_tab_label(child)
            title = web_view.props.title
            if not title:
                title = web_view.props.uri
            label.set_label_text(title)
        
    """def _new_web_view_request_cb (self, web_view, web_frame):
        view = self.new_tab()
        view.connect("web-view-ready", self._new_web_view_ready_cb)
        return view"""

    def _new_web_view_request_cb (self, web_view, navigation_action):
        type_ =  navigation_action.get_navigation_type()
        if type_ == 5:
            view = self.new_tab()
            view.connect("ready-to-show", self._new_web_view_ready_cb)
        return view

    def _new_web_view_ready_cb (self, web_view):
        self.emit("new-window-requested", web_view)

class ThIndexerWindow(Gtk.Window):
    def __init__(self, main):
        Gtk.Window.__init__(self)
        self.main = main
        self.connect('delete-event', lambda w,*a: w.hide() or True)
        self.set_title(_('Manage search index'))
        self.set_type_hint(Gdk.WindowTypeHint.DIALOG)
        self.set_modal(True)
        self.set_transient_for(main)
        self.main = main
        self.set_position(Gtk.WindowPosition.CENTER_ON_PARENT)
        vb = Gtk.VBox(False,2); self.add(vb)
        hb = Gtk.HBox(False,2); vb.pack_start(hb, False, False, 0)
        self.progress = Gtk.ProgressBar()
        self.progress.set_show_text(True)
        self.progress.set_text("")
        self.start_b = b = Gtk.Button(_("Queue new books"))
        b.connect('clicked', self.indexNew)
        hb.pack_start(b, False, False, 0)
        hb.pack_start(self.progress, False, False, 0)
        self.cancel_b = b = Gtk.Button(stock = Gtk.STOCK_CLOSE)
        #b.connect('clicked', self.cancel_cb)
        b.connect('clicked', lambda w,*a: self.hide() or True)
        hb.pack_start(b, False, False, 0)
        #b.set_sensitive(False)
        #self.update()
        
    def cancel_cb(self, *w):
        return False
        if self.main.th.asyncIndexer.started:
            self.main.th.asyncIndexer.cancelQueued()
            self.start_b.set_sensitive(True)
            self.cancel_b.set_sensitive(False)
            self.progress.set_text(_("Indexing jobs canceled"))
            return False
    
    def indexNew(self, *a):
        self.start_b.set_sensitive(False)
        #self.cancel_b.set_sensitive(True)
        self.main.th.asyncIndexer.queueIndexNew()
        if not self.main.th.asyncIndexer.started:
            self.main.th.asyncIndexer.start()
        self.update()
        #GLib.timeout_add(250, self.update)
        
    def update(self, *a):
        #if not self.get_property('visible'):
        #    return True
        jj = j = self.main.th.asyncIndexer.jobs()
        while (j > 0 and self.main.get_property('visible')):
            self.progress.set_text (_("Indexing ... (%d left)") % j)
            self.progress.pulse()
            j = self.main.th.asyncIndexer.jobs()
            Gtk.main_iteration()
            #Gtk.main_iteration_do(True)
        self.progress.set_text (_("No indexing jobs left"))
        self.start_b.set_sensitive(True)
        if j <= 0 and jj > 0:
            info(_("Indexing %d jobs, Done") % jj, self.main)
        #self.cancel_b.set_sensitive(False)
        return True

class ThFixesWindow(Gtk.Window):
    def __init__(self, main):
        Gtk.Window.__init__(self)
        self.set_title(_('Misc. Fixes'))
        self.set_type_hint(Gdk.WindowTypeHint.DIALOG)
        self.set_modal(True)
        self.set_transient_for(main)
        self.main = main
        self.set_position(Gtk.WindowPosition.CENTER_ON_PARENT)
        self.connect('delete-event', lambda w,*a: w.hide() or True)
        self.set_deletable(True)

        vb = Gtk.VBox(False,2); self.add(vb)
        hb = Gtk.HBox(False,2); vb.pack_start(hb, False, False, 0)
        l = Gtk.Label()
        l.set_markup(_("""<span size = "large">Those procedures are to be used in case of <b>emergency</b> only,
for example to recover power failure.</span>"""))
        hb.pack_start(l , False, False, 0)

        hb = Gtk.HBox(False,2); vb.pack_start(hb, False, False, 0)
        b = Gtk.Button(_('remove search index'))
        b.set_tooltip_text(_('you will need to re-index all books'))
        hb.pack_start(b , False, False, 0)
        b.connect('clicked', self.rm_index_cb)
        
        hb = Gtk.HBox(False,2); vb.pack_start(hb, False, False, 0)
        b = Gtk.Button(_('remove meta data cache to generate a fresh one'))
        b.set_tooltip_text(_('instead of incremental meta data gathering'))
        hb.pack_start(b , False, False, 0)
        b.connect('clicked', self.rm_mcache_cb)
        
        b = Gtk.Button(stock = Gtk.STOCK_CLOSE)
        hb.pack_end(b , False, False, 0)
        b.connect('clicked', lambda w,*a: self.hide() or True)
        #self.show_all()

    def rm_index_cb(self, b):
        if not sure(_("You will need to recreate search index in-order to search again.\nAre you sure you want to remove search index?"), self.main): return
        p = os.path.join(self.main.th.prefixes[0], 'index')
        try:
            shutil.rmtree(p)
        except OSError:
            error(_("unable to remove folder [%s]" % p), self.main)
        else:
            info(_("Done"), self.main)

    def rm_mcache_cb(self, b):
        if not sure(_("Are you sure you want to remove search meta data cache?"), self.main): return
        p = os.path.join(self.main.th.prefixes[0], 'cache', 'meta.db')
        try:
            os.unlink(p)
        except OSError:
            error(_("unable to remove file [%s]" % p), self.main)
        else:
            self.main.th.reconstructMetaIndexedFlags()
            info(_("Done"), self.main)

class ThMainWindow(Gtk.ApplicationWindow):
    def __init__(self, th, port, server):
        self.th = th
        self.port = port
        self.server = server # we need this to quit the server when closing main window
        Gtk.Window.set_default_icon_name('thawab')
        Gtk.Window.__init__(self)
        self.set_title(_('Thawab'))
        self.set_default_size(600, 480)
        self.maximize()
        self.fixes_w = ThFixesWindow(self)
        self.import_w = ThImportWindow(self)
        self.ix_w = ThIndexerWindow(self)
        
        vb = Gtk.VBox(False,0); self.add(vb)
        ghead = Gtk.HeaderBar()
        ghead.set_show_close_button(True)
        ghead.props.title = _('Thawab')
        self.set_titlebar(ghead)
        tools = Gtk.Toolbar()
        #vb.pack_start(tools, False, False, 2)




        m_button = Gtk.MenuButton()
        ghead.pack_end(m_button)
        
        m_model = Gio.Menu()
        mi = Gio.MenuItem().new(_("Create search index"),"win.index")
        icon = Gio.ThemedIcon().new("system-run")
        mi.set_icon(icon)
        m_model.append_item(mi)
        
        mi = Gio.MenuItem().new(_("Misc Fixes"),"win.fixes")
        icon = Gio.ThemedIcon().new("edit-clear")
        mi.set_icon(icon)
        m_model.append_item(mi)
        
        mi = Gio.MenuItem().new(_("Help"),"win.help")
        icon = Gio.ThemedIcon().new("help-about")
        mi.set_icon(icon)
        m_model.append_item(mi)
        m_button.set_menu_model(m_model)
        
        m_action = Gio.SimpleAction.new("index", None)
        m_action.connect("activate",  lambda *a: self.ix_w.show_all())
        self.add_action(m_action)
        m_action = Gio.SimpleAction.new("fixes", None)
        m_action.connect("activate",  self.fixes_cb)
        self.add_action(m_action)
        m_action = Gio.SimpleAction.new("help", None)
        m_action.connect("activate",  lambda *a: self._content.new_tab ("http://127.0.0.1:%d/_theme/manual/manual.html" % port))
        self.add_action(m_action)
        
        self.axl = Gtk.AccelGroup()
        self.add_accel_group(self.axl)
        ACCEL_CTRL_KEY, ACCEL_CTRL_MOD = Gtk.accelerator_parse("<Ctrl>")
        ACCEL_SHFT_KEY, ACCEL_SHFT_MOD = Gtk.accelerator_parse("<Shift>")
        img = Gtk.Image()
        img.set_from_stock(Gtk.STOCK_ZOOM_IN, Gtk.IconSize.BUTTON)
        b = Gtk.ToolButton(icon_widget = img, label = _("Zoom in"))
        b.add_accelerator("clicked", self.axl, Gdk.KEY_equal, ACCEL_CTRL_MOD, Gtk.AccelFlags.VISIBLE)
        b.add_accelerator("clicked", self.axl, Gdk.KEY_plus, ACCEL_CTRL_MOD, Gtk.AccelFlags.VISIBLE)
        b.add_accelerator("clicked", self.axl, Gdk.KEY_KP_Add, ACCEL_CTRL_MOD, Gtk.AccelFlags.VISIBLE)
        b.set_is_important(True)
        b.set_tooltip_text("{}\t‪{}‬".format(_("Makes things appear bigger"), "(Ctrl++)"))
        b.connect('clicked', lambda a: self._do_in_current_view("zoom_in"))
        ghead.pack_end(b)
        
        img = Gtk.Image()
        img.set_from_stock(Gtk.STOCK_ZOOM_100, Gtk.IconSize.BUTTON)
        b = Gtk.ToolButton(icon_widget = img, label = _("1:1 Zoom"))
        b.add_accelerator("clicked", self.axl, ord('0'), ACCEL_CTRL_MOD, Gtk.AccelFlags.VISIBLE)
        b.add_accelerator("clicked", self.axl, Gdk.KEY_KP_0, ACCEL_CTRL_MOD, Gtk.AccelFlags.VISIBLE)
        b.set_tooltip_text("{}\t{}".format(_("Restore original zoom factor"), "(Ctrl+0)"))
        b.connect('clicked', lambda a: self._do_in_current_view("set_zoom_level",1.0))
        ghead.pack_end(b)
        
        img = Gtk.Image()
        img.set_from_stock(Gtk.STOCK_ZOOM_OUT, Gtk.IconSize.BUTTON)
        b = Gtk.ToolButton(icon_widget = img, label = _("Zoom out"))
        b.add_accelerator("clicked", self.axl, Gdk.KEY_minus, ACCEL_CTRL_MOD, Gtk.AccelFlags.VISIBLE)
        b.add_accelerator("clicked", self.axl, Gdk.KEY_KP_Subtract, ACCEL_CTRL_MOD, Gtk.AccelFlags.VISIBLE)
        b.set_tooltip_text("{}\t‪{}‬".format(_("Makes things appear smaller"), "(Ctrl+-)"))
        b.connect('clicked', lambda a: self._do_in_current_view("zoom_out"))
        ghead.pack_end(b)
        
        self._content =  ContentPane("http://127.0.0.1:%d/" % port, _("Thawab"))
        vb.pack_start(self._content,True, True, 0)
        

        
        b = Gtk.ToolButton.new_from_stock(Gtk.STOCK_NEW)
        b.connect('clicked', lambda bb: self._content.new_tab())
        b.add_accelerator("clicked", self.axl, ord('n'), ACCEL_CTRL_MOD, Gtk.AccelFlags.VISIBLE)
        b.set_tooltip_text("{}\t‪{}‬".format(_("Open a new tab"), "(Ctrl+N)" ))
        #tools.insert(b, -1)
        ghead.pack_start(b)

        # TODO: add navigation buttons (back, forward ..etc.) and zoom buttons
        tools.insert(Gtk.SeparatorToolItem(), -1)

        img = Gtk.Image()
        img.set_from_stock(Gtk.STOCK_CONVERT, Gtk.IconSize.BUTTON)
        b = Gtk.ToolButton.new(icon_widget = img, label = _("Import"))
        b.set_tooltip_text(_("Import .bok files"))
        b.connect('clicked', self.import_cb)
        #tools.insert(b, -1)
        ghead.pack_start(b)

        img = Gtk.Image()
        img.set_from_stock(Gtk.STOCK_FIND_AND_REPLACE, Gtk.IconSize.BUTTON)
        b = Gtk.ToolButton(icon_widget = img, label = _("Index"))
        b.set_is_important(True)
        b.set_tooltip_text(_("Create search index"))
        b.connect('clicked', lambda *a: self.ix_w.show_all())
        tools.insert(b, -1)

        tools.insert(Gtk.SeparatorToolItem(), -1)


        tools.insert(Gtk.SeparatorToolItem(), -1)

        img = Gtk.Image()
        img.set_from_stock(Gtk.STOCK_PREFERENCES, Gtk.IconSize.BUTTON)
        b = Gtk.ToolButton(icon_widget = img, label = _("Fixes"))
        b.set_is_important(True)
        b.set_tooltip_text(_("Misc Fixes"))
        b.connect('clicked', self.fixes_cb)
        tools.insert(b, -1)

        tools.insert(Gtk.SeparatorToolItem(), -1)

        img = Gtk.Image()
        img.set_from_stock(Gtk.STOCK_HELP, Gtk.IconSize.BUTTON)
        b = Gtk.ToolButton(icon_widget = img, label = _("Help"))
        b.set_tooltip_text(_("Show user manual"))
        b.connect('clicked', lambda a: self._content.new_tab ("http://127.0.0.1:%d/_theme/manual/manual.html" % port))
        tools.insert(b, -1)
        
        self._content.new_tab()

        self.connect("delete_event", self.quit)
        self.connect("destroy", self.quit)
        ## prepare dnd 
        self.drag_dest_set(Gtk.DestDefaults.ALL, [], Gdk.DragAction.COPY)
        self.drag_dest_set_target_list(targets)
        self.connect('drag-data-received', self.drop_data_cb)
        
        self.show_all()

    def _do_in_current_view (self, action, *a, **kw):
         n = self._content.get_current_page()
         if n < 0:
            return
         #view = self._content.get_nth_page(n).get_child()
         view = self._content.get_nth_page(n).get_child().get_child()
         getattr(view, action)(*a,**kw)

    def _do_in_all_views (self, action, *a, **kw):
         for n in range(self._content.get_n_pages()):
             #view = self._content.get_nth_page(n).get_child()
             view = self._content.get_nth_page(n).get_child().get_child()
             getattr(view, action)(*a,**kw)


    def fixes_cb(self, *b):
        if not self.fixes_w:
            self.fixes_w = ThFixesWindow(self)
        self.fixes_w.show_all()

    def drop_data_cb(self, widget, dc, x, y, selection_data, info, t):
        if not self.import_w:
            self.import_w = ThImportWindow(self)
        for i in selection_data.get_uris():
            self.import_w.add_uri(i)
        self.import_w.show_all()
        #dc.drop_finish (True, t);


    def import_cb(self, b):
        if not self.import_w:
            self.import_w = ThImportWindow(self)
        self.import_w.show_all()

    def quit(self,*args):
        #if self.import_w.cancel_b.get_sensitive():
        #    self.import_w.show()
        #    return True
        #if not self.ix_w.start_b.get_sensitive():
        #    self.ix_w.show_all()
        #    return True
        self.server.running = False
        Gtk.main_quit()
        return False

THAWAB_HIGH_PORT = 18080

def launchServer():
    exedir = os.path.dirname(sys.argv[0])
    th = Thawab.core.ThawabMan(isMonolithic = False)
    lookup = [
        os.path.join(exedir,'thawab-themes'),
        os.path.join(exedir,'..','share','thawab','thawab-themes'),
    ]
    lookup.extend(map(lambda i: os.path.join(i, 'themes'), th.prefixes))
    app = webApp(th,
                 'app',
                 lookup,
                 th.conf.get('theme', 'default'),
                 '/_theme/',)
    launched = False
    port = THAWAB_HIGH_PORT
    while(not launched):
        try:
            server = httpserver.serve(app,
                                      host = '127.0.0.1',
                                      port = port,
                                      start_loop = False)
        except socket.error:
            port += 1
        else:
            launched = True
    return th, port, server

def onlyterminal(): #To run thawab by terminal only by thawab-server
    exedir = os.path.dirname(sys.argv[0])
    ld = os.path.join(exedir,'..','share','locale')
    if not os.path.isdir(ld):
        ld = os.path.join(exedir, 'locale')
    gettext.install('thawab', ld, unicode = 0)
    th, port, server = launchServer()

    try:
        thread=threading.Thread(target=server.serve_forever, args=())
        thread.daemon=True
        thread.start()
        while True: time.sleep(100)
    except (KeyboardInterrupt, SystemExit):
        print '\nHope to made a nice time, Ojuba team <ojuba.org>.\n'
        os._exit(0)
        
def main():
    exedir = os.path.dirname(sys.argv[0])
    ld = os.path.join(exedir,'..','share','locale')
    if not os.path.isdir(ld):
        ld = os.path.join(exedir, 'locale')
    gettext.install('thawab', ld, unicode = 0)
    th, port, server = launchServer()

    GObject.threads_init()
    Gdk.threads_init()

    threading.Thread(target=server.serve_forever, args=()).start()
    while(not server.running):
        time.sleep(0.25)
    Gdk.threads_enter()
    w = ThMainWindow(th, port,server)
    Gtk.main()
    Gdk.threads_leave()

if __name__  ==  "__main__":
    main()
