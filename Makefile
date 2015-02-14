APPNAME=thawab
DESTDIR?=/
DATADIR?=$(DESTDIR)/usr/share

SOURCES=$(wildcard *.desktop.in)
TARGETS=${SOURCES:.in=}

ECHO := echo
MAKE := make
PYTHON := python2
INSTALL := install
INTLTOOL_MERGE := intltool-merge
RM := $(shell which rm | egrep '/' | sed  's/\s//g')
GTK_UPDATE_ICON_CACHE := $(shell which gtk-update-icon-cache)
UPDATE_DESKTOP_DATABASE := $(shell which update-desktop-database)

all: $(TARGETS) icons

icons:
	@for i in 96 72 64 48 36 32 24 22 16; do \
		convert -background none $(APPNAME).svg -resize $${i}x$${i} $(APPNAME)-$${i}.png; \
	done
pos:
	$(MAKE) -C po all

install: locale
	@$(ECHO) "*** Installing..."
	@$(PYTHON) setup.py install -O2 --root $(DESTDIR)
	@$(ECHO) "Copying: $(APPNAME).desktop -> $(DATADIR)/applications/"
	@$(INSTALL) -d $(DATADIR)/applications/
	@$(INSTALL) -d $(DATADIR)/$(APPNAME)/
	@$(INSTALL) -m 0644 $(APPNAME).desktop $(DATADIR)/applications/
	@$(INSTALL) -m 0644 -D $(APPNAME).svg $(DATADIR)/icons/hicolor/scalable/apps/$(APPNAME).svg;
	@for i in 96 72 64 48 36 32 24 22 16; do \
		$(INSTALL) -d $(DATADIR)/icons/hicolor/$${i}x$${i}/apps; \
		$(INSTALL) -m 0644 -D $(APPNAME)-$${i}.png $(DATADIR)/icons/hicolor/$${i}x$${i}/apps/$(APPNAME).png; \
	done
	@$(RM) -rf build
	@$(DESTDIR)/$(UPDATE_DESKTOP_DATABASE) --quiet $(DATADIR)/applications  &> /dev/null || :
	@$(DESTDIR)/$(GTK_UPDATE_ICON_CACHE) --quiet $(DATADIR)/icons/hicolor &> /dev/null || :

uninstall: 
	@$(ECHO) "*** Uninstalling..."
	@$(ECHO) "- Removing: $(DATADIR)/applications/$(APPNAME).desktop"
	@$(RM) -f $(DATADIR)/applications/$(APPNAME).desktop
	@$(ECHO) "- Removing: $(DESTDIR)/usr/share/locale/*/LC_MESSAGES/$(APPNAME).mo"
	@$(RM) -f $(DESTDIR)/usr/share/locale/*/LC_MESSAGES/$(APPNAME).mo
	@$(ECHO) "- Removing: $(DESTDIR)/usr/bin/$(APPNAME)"
	@$(RM) -f $(DESTDIR)/usr/bin/$(APPNAME)-gtk
	@$(RM) -f $(DESTDIR)/usr/bin/$(APPNAME)-server	
	@$(ECHO) "- Removing: $(DESTDIR)/usr/lib/python*/*-packages/Thawab"
	@$(RM) -rf $(DESTDIR)/usr/lib/python*/*-packages/Thawab
	@$(ECHO) "- Removing: $(DESTDIR)/usr/lib/python*/*-packages/$(APPNAME)*"
	@$(RM) -rf $(DESTDIR)/usr/lib/python*/*-packages/$(APPNAME)*
	@$(ECHO) "- Removing: $(DESTDIR)/usr/share/$(APPNAME)"
	@$(RM) -rf $(DESTDIR)/usr/share/$(APPNAME)
	
	@$(ECHO) "- Removing: $(DESTDIR)/usr/*/share/locale/*/LC_MESSAGES/$(APPNAME).mo"
	@$(RM) -f $(DESTDIR)/usr/*/share/locale/*/LC_MESSAGES/$(APPNAME).mo
	@$(ECHO) "- Removing: $(DESTDIR)/usr/*/bin/$(APPNAME)"
	@$(RM) -f $(DESTDIR)/usr/*/bin/$(APPNAME)-gtk
	@$(RM) -f $(DESTDIR)/usr/*/bin/$(APPNAME)-server	
	@$(ECHO) "- Removing: $(DESTDIR)/usr/*/lib/python*/*-packages/Thawab"
	@$(RM) -rf $(DESTDIR)/usr/*/lib/python*/*-packages/Thawab
	@$(ECHO) "- Removing: $(DESTDIR)/usr/*/lib/python*/*-packages/$(APPNAME)*"
	@$(RM) -rf $(DESTDIR)/usr/*/lib/python*/*-packages/$(APPNAME)*
	@$(ECHO) "- Removing: $(DESTDIR)/usr/*/share/$(APPNAME)"
	@$(RM) -rf $(DESTDIR)/usr/*/share/$(APPNAME)
	
	@$(RM) -f $(DATADIR)/icons/hicolor/scalable/apps/$(APPNAME).svg
	@$(RM) -f $(DATADIR)/icons/hicolor/*/apps/$(APPNAME).png;
	@$(DESTDIR)/$(UPDATE_DESKTOP_DATABASE) --quiet $(DATADIR)/applications  &> /dev/null || :
	@$(DESTDIR)/$(GTK_UPDATE_ICON_CACHE) --quiet $(DATADIR)/icons/hicolor &> /dev/null || :
	
%.desktop: %.desktop.in pos
	intltool-merge -d po $< $@

clean:
	@$(ECHO) "*** Cleaning..."
	@$(MAKE) -C po clean
	@$(ECHO) "- Removing: $(TARGETS)"
	@$(RM) -f $(TARGETS)
	@$(ECHO) "- Removing: locale build"
	@$(RM) -rf locale build
	@$(ECHO) "- Removing: *.pyc"
	@$(RM) -f *.pyc
	@$(ECHO) "- Removing: */*.pyc"
	@$(RM) -f */*.pyc
	@$(ECHO) "- Removing: $(APPNAME)-*.png"
	@$(RM) -f $(APPNAME)-*.png
	@$(ECHO) "- Removing Cache directories"
	@$(RM) -f thawab-data/user.db
	@$(RM) -rf thawab-data/cache
	@$(RM) -rf thawab-data/index
	@$(RM) -rf thawab-data/tmp
	@$(RM) -rf thawab-data/db
	@$(RM) -rf thawab-data/conf
