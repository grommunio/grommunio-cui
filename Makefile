MKDIR_P = mkdir -p
SED = sed
PACKAGE_NAME = grommunio-cui
prefix = /usr
sbindir = ${prefix}/sbin
libexecdir = ${prefix}/libexec
datadir = ${prefix}/share
pkglibexecdir = ${libexecdir}/${PACKAGE_NAME}
unitdir = /usr/lib/systemd/system

locales = de en
mo_files = $(patsubst %,locale/%/LC_MESSAGES/cui.mo,${locales})

all: ${mo_files}

%.mo: %.po
	msgfmt -o $@ $<

install: ${mo_files}
	${MKDIR_P} ${DESTDIR}${pkglibexecdir}/cui ${DESTDIR}${sbindir} ${DESTDIR}${unitdir}
	cp -afv getty *.py ${DESTDIR}${pkglibexecdir}/
	cp -afv setlogcons.service ${DESTDIR}${unitdir}/
	# overwrite desired
	cp -afv cui/*.py ${DESTDIR}${pkglibexecdir}/cui/
	${SED} 's!@pkglibexecdir@!${pkglibexecdir}!g' <grommunio-cui.in >${DESTDIR}${sbindir}/grommunio-cui
	chmod a+x ${DESTDIR}${sbindir}/grommunio-cui
	${SED} 's!@pkglibexecdir@!${pkglibexecdir}!g' <grommunio-cui@.service.in >${DESTDIR}${unitdir}/grommunio-cui@.service
	for i in ${locales}; do \
		t=${DESTDIR}${datadir}/locale/$$i/LC_MESSAGES; \
		${MKDIR_P} $$t && cp -av locale/$$i/LC_MESSAGES/cui.mo $$t/; \
	done

clean:
	rm -fv locale/*/LC_MESSAGES/*.mo
