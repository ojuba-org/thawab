POTFILE=$(shell cat POTFILES.in)
SOURCES=$(addprefix ../, $(POTFILE))
POFILES=$(wildcard *.po)
MOFILES=$(patsubst %.po,%.mo,$(POFILES))

all: thawab.pot $(MOFILES)

thawab.pot: $(SOURCES)
	intltool-update -g thawab -p

%.mo: %.po
	msgfmt $*.po -o $*.mo
	mkdir -p ../locale/$*/LC_MESSAGES/ || :
	cp $*.mo ../locale/$*/LC_MESSAGES/thawab.mo

%.po: thawab.pot
	intltool-update -g thawab -d $*

