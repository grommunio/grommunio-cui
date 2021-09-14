MKDIR_P = mkdir -p
SED = sed
PACKAGE_NAME = grommunio-cui
prefix = /usr
sbindir = ${prefix}/sbin
libexecdir = ${prefix}/libexec
pkglibexecdir = ${libexecdir}/${PACKAGE_NAME}
unitdir = /usr/lib/systemd/system

install:
	${MKDIR_P} ${DESTDIR}${pkglibexecdir} ${DESTDIR}${sbindir} ${DESTDIR}${unitdir}
	cp -afv getty *.py ${DESTDIR}${pkglibexecdir}/
	# overwrite desired
	cp -afv cui/*.py ${DESTDIR}${pkglibexecdir}/
	${SED} 's!@pkglibexecdir@!${pkglibexecdir}!g' <grommunio-cui.in >${DESTDIR}${sbindir}/grommunio-cui
	chmod a+x ${DESTDIR}${sbindir}/grommunio-cui
	${SED} 's!@pkglibexecdir@!${pkglibexecdir}!g' <grommunio-cui@.service.in >${DESTDIR}${unitdir}/grommunio-cui@.service
