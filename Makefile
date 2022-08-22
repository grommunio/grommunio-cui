MKDIR_P = mkdir -p
SED = sed
PACKAGE_NAME = grommunio-cui
prefix = /usr
sbindir = ${prefix}/sbin
libexecdir = ${prefix}/libexec
pkglibexecdir = ${libexecdir}/${PACKAGE_NAME}
unitdir = /usr/lib/systemd/system

all: locale/de/LC_MESSAGES/cui.mo locale/en/LC_MESSAGES/cui.mo

%.mo: %.po
	msgfmt -o $@ $<

install:
	${MKDIR_P} ${DESTDIR}${pkglibexecdir}/cui ${DESTDIR}${sbindir} ${DESTDIR}${unitdir}
	cp -afv getty *.py ${DESTDIR}${pkglibexecdir}/
	cp -afv setlogcons.service ${DESTDIR}${unitdir}/
	# overwrite desired
	cp -afv cui/*.py ${DESTDIR}${pkglibexecdir}/cui/
	${SED} 's!@pkglibexecdir@!${pkglibexecdir}!g' <grommunio-cui.in >${DESTDIR}${sbindir}/grommunio-cui
	chmod a+x ${DESTDIR}${sbindir}/grommunio-cui
	${SED} 's!@pkglibexecdir@!${pkglibexecdir}!g' <grommunio-cui@.service.in >${DESTDIR}${unitdir}/grommunio-cui@.service
