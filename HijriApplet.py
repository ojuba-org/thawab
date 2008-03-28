#! /usr/bin/env python
# -*- coding: utf-8 -*-
"""
Hijri Tray Applet for GNOME (also works with KDE)
Copyright (c) 2006-2008 Muayyad Saleh Alsadi<alsadi@gmail.com>
Based on an enhanced algorithm designed by me
the algorithm is discussed in a book titled "حتى لا ندخل جحور الضباب"
(not yet published)

The algorith itself is not here, it's in another file called hijri.py
"""

# TODO: Implement about dialog
# TODO: Implement ocations reminder
# TODO: Implement goto today button
# TODO: Implement a way to jump to an arbitrary date
# TODO: Implement configuration, ie. allow direction change, and setting first way of week

import time
import gtk
import gobject
import egg.trayicon
import pynotify

from HijriCal import HijriCal
cal=HijriCal()
win,accel,title=None,None,None
notify,tips,tr,box,l,popup_menu=None,None,None,None,None,None
week_days=[ "الأحد", "الإثنين", "الثلاثاء", "الاربعاء", "الخميس", "الجمعة", "السبت" ]
months=[
  "محرم","صفر","ربيع الاول","ربيع الثاني",
  "جمادى الأولى","جمادى الثانية","رجب","شعبان",
  "رمضان","شوال","ذو القعدة","ذو الحجة"
  ]
gmonths=[
  "كانون ثاني", "شباط", "آذار", "نيسان",
  "أيار", "حزيران","تموز","آب",
  "أيلول", "تشرين أول", "تشرين ثاني", "كانون أول"
  ]
cell=[[None]*7,[None]*7,[None]*7,[None]*7,[None]*7,[None]*7]
days_l=[None]*7
def main():
	global cal
	global notify, tips,tr,box,l
	pynotify.init('HijriApplet')
	notify=pynotify.Notification("التقويم الهجري")
	Y,M,D,W=cal.today
	yy,mm,dd=cal.g_today
	tr = egg.trayicon.TrayIcon("HijriApplet")
	box = gtk.EventBox()
	l=gtk.Label()
	l.set_markup('<span size="small" weight="bold" foreground="red" background="#ffffff">%02d</span>\n<span size="small" weight="bold" foreground="yellow" background="black">%02d</span>' % (D, M))
	tr.add(box)
	box.add(l)
	try: box.set_tooltip_text("Waiting ...")
	except: tips=gtk.Tooltips()

	set_tip(box, "%s, %d من %s لعام %d" % (week_days[W], D, months[M-1], Y))
	#notify.attach_to_widget(w) # whats wrong with it
	#notify.set_property('attach-widget',box)
	notify.set_property('icon-name','gtk-info')
	notify.set_property('summary', "التقويم الهجري" )
	notify.set_property('body', "%s, %d من %s لعام %d\nالموافق %d من %s لعام %s" % (week_days[W], D, months[M-1], Y,dd,gmonths[mm-1],yy) )
	notify.show()

	setup_popup_menu()

	#update()
	#gobject.timeout_add(1000, update)

	tr.show_all()
	build_gui()
	print "Done"
	gtk.main()
def wday_index(i):
	ws=cal.get_week_start()
	if (cal.get_direction()==1): return (i+ws) % 7
	else: return ((6-i)+ws) % 7

def hide_cb(*args): win.hide(); return True
def build_gui():
	global cell,days_l,win,accel,title
	accel=gtk.AccelGroup()
	win = gtk.Window(); win.set_title('التقويم الهجري')
	win.add_accel_group(accel)
	win.hide_on_delete()
	#win.set_size_request(200, 300)
	win.connect('delete-event', hide_cb)
	
	vb=gtk.VBox(False,0); win.add(vb)
	hb=gtk.HBox(False,0)
	vb.pack_start(hb,False, False, 0)
	title=gtk.Label(months[cal.M-1]+" "+str(cal.Y))
	img=gtk.Image(); img.set_from_stock(gtk.STOCK_GOTO_FIRST, gtk.ICON_SIZE_SMALL_TOOLBAR)
	btn=gtk.Button(); btn.add(img)
	btn.connect('clicked', prev_year_cb)
	hb.pack_start(btn,False, False, 0)
	img=gtk.Image(); img.set_from_stock(gtk.STOCK_GO_BACK, gtk.ICON_SIZE_SMALL_TOOLBAR)
	btn=gtk.Button(); btn.add(img)
	btn.connect('clicked', prev_month_cb)
	
	hb.pack_start(btn,False, False, 0)
	
	hb.pack_start(title,True, True, 0)

	img=gtk.Image(); img.set_from_stock(gtk.STOCK_GO_FORWARD, gtk.ICON_SIZE_SMALL_TOOLBAR)
	btn=gtk.Button(); btn.add(img)
	btn.connect('clicked', next_month_cb)
	
	hb.pack_start(btn,False, False, 0)
	img=gtk.Image(); img.set_from_stock(gtk.STOCK_GOTO_LAST, gtk.ICON_SIZE_SMALL_TOOLBAR)
	btn=gtk.Button(); btn.add(img)
	btn.connect('clicked', next_year_cb)
	
	hb.pack_start(btn,False, False, 0)


	table = gtk.Table(7,6,True)
	vb.pack_start(table,True, True, 0)
	a=cal.get_array()
	b=cal.get_g_array()
	for i in xrange(7):
		days_l[i]=gtk.Label(week_days[wday_index(i)])
		table.attach(days_l[i],i,i+1,0,1,gtk.FILL | gtk.EXPAND,gtk.FILL | gtk.EXPAND,0,0)
	for n in xrange(42):
		i=n%7; j=n/7;
		cell[j][i]=gtk.Label("-")
		cell[j][i].set_alignment(0.5,0.5)
		cell[j][i].set_justify(gtk.JUSTIFY_CENTER)
		if (a[j][i]): cell[j][i].set_markup('<span size="large" weight="bold" foreground="#004000" background="#ffffff">%02d</span>\n<span size="small" weight="bold" foreground="gray">%02d/%02d</span>' % (a[j][i], b[j][i][0],b[j][i][1]))
		table.attach(cell[j][i],i,i+1,j+1,j+2,gtk.FILL | gtk.EXPAND,gtk.FILL | gtk.EXPAND,0,0)
        win.show_all()
def update_gui():
	global cell,days_l,title
	title.set_text(months[cal.M-1]+" "+str(cal.Y))
	a=cal.get_array()
	b=cal.get_g_array()
	for i in xrange(7):
		days_l[i].set_text(week_days[wday_index(i)])
	for n in xrange(42):
		i=n%7; j=n/7;
		if (a[j][i]): cell[j][i].set_markup('<span size="large" weight="bold" foreground="#004000" background="#ffffff">%02d</span>\n<span size="small" weight="bold" foreground="gray">%02d/%02d</span>' % (a[j][i], b[j][i][0],b[j][i][1]))
		else: cell[j][i].set_text('-')
def prev_year_cb(*args):
	cal.goto_hijri_day(cal.Y-1, cal.M, 1)
	update_gui()
def next_year_cb(*args):
	cal.goto_hijri_day(cal.Y+1, cal.M, 1)
	update_gui()	
def prev_month_cb(*args):
	Y,M,D=cal.Y,cal.M-1,1
	if (M<1): M=12; Y-=1
	cal.goto_hijri_day(Y, M, 1); update_gui()
def next_month_cb(*args):
	Y,M,D=cal.Y,cal.M+1,1
	if (M>12): M=1; Y+=1
	cal.goto_hijri_day(Y, M, 1); update_gui()

def setup_popup_menu():
	global popup_menu,box
	box.connect("button-press-event", clicked_cb)
	popup_menu = gtk.Menu()
	#for j in xrange(10):
	#	i=gtk.MenuItem(str(j),False); popup_menu.add(i)
	#popup_menu.add(gtk.SeparatorMenuItem())
	i = gtk.ImageMenuItem("Show")
        i.connect('activate', show_cb)
        popup_menu.add(i)
	i = gtk.ImageMenuItem("Hide")
        i.connect('activate', lambda *args: win.hide())
        popup_menu.add(i)
	
	i = gtk.ImageMenuItem(gtk.STOCK_ABOUT)
        i.connect('activate', about_cb)
        popup_menu.add(i)
	i = gtk.ImageMenuItem(gtk.STOCK_QUIT)
        i.connect('activate', gtk.main_quit)
        popup_menu.add(i)

def clicked_cb(widget, event):
	if event.button == 1: win.show()
	if event.button == 3: show_popup_menu()

def show_cb(*args): win.show_all()
def about_cb(*args): print "about"

def show_popup_menu():
	global popup_menu
        popup_menu.show_all()
	popup_menu.popup(None, None, None, 3, gtk.get_current_event_time())

def set_tip(w,txt):
   global tips
   if tips: tips.set_tip(w, txt)
   else: w.set_tooltip_text(txt)

main()
