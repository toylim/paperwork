VERSION_FILE = src/paperwork_gtk/_version.py
PYTHON ?= python3

build: build_c build_py

install: install_py install_c

uninstall: uninstall_py

build_py: ${VERSION_FILE} l10n_compile
	${PYTHON} ./setup.py build

build_c:

version: ${VERSION_FILE}

${VERSION_FILE}:
	echo "# -*- coding: utf-8 -*-" >| $@
	echo -n "version = \"" >> $@
	echo -n $(shell git describe --always) >> $@
	$(eval branch_name = $(shell git symbolic-ref HEAD 2>/dev/null))
	if [ -n "${branch_name}" ] && [ "${branch_name}" != "refs/heads/master" ] ; then echo -n "-${branch_name}" >> $@ ; fi
	echo "\"" >> $@
	echo "authors_code = \"\"\"" >> $@
	echo "    Code contributors:" >> $@
	git shortlog -sne >> $@
	echo "\"\"\"" >> $@
	echo >> $@
	cat ../AUTHORS.py >> $@

doc:

upload_doc:

data:
	$(MAKE) -C src/paperwork_gtk/model/help data
	$(MAKE) -C src/paperwork_gtk/icon data

check:
	flake8 --exclude=_version.py src/paperwork_gtk

test: install
	python3 -m unittest discover --verbose -s tests

windows_exe:
	${PYTHON} /mingw32/bin/pip3-script.py install .
	${PYTHON} ./setup.py build_exe
	mkdir -p $(CURDIR)/../build/exe
	mv $$(find $(CURDIR)/build -type d -name exe\*)/* $(CURDIR)/../build/exe
	# ugly, but "import pkg_resources" doesn't work in frozen environments
	# and I don't want to have to patch the build machine to fix it every
	# time.
	mkdir -p $(CURDIR)/../build/exe/data
	(cd $(CURDIR)/src && find . -name '*.css' -exec cp --parents \{\} $(CURDIR)/../build/exe/data \; )
	(cd $(CURDIR)/src && find . -name '*.glade' -exec cp --parents \{\} $(CURDIR)/../build/exe/data \; )
	(cd $(CURDIR)/src && find . -name '*.mo' -exec cp --parents \{\} $(CURDIR)/../build/exe/data \; )
	(cd $(CURDIR)/src && find . -name '*.pdf' -exec cp --parents \{\} $(CURDIR)/../build/exe/data \; )
	(cd $(CURDIR)/src && find . -name '*.png' -exec cp --parents \{\} $(CURDIR)/../build/exe/data \; )

linux_exe:

release:
ifeq (${RELEASE}, )
	@echo "You must specify a release version (make release RELEASE=1.2.3)"
else
	@echo "Will release: ${RELEASE}"
	@echo "Checking release is in ChangeLog ..."
	grep ${RELEASE} ChangeLog | grep -v "/xx"
	@echo "Checking release is in data/work.openpaper.Paperwork.appdata.xml ..."
	grep ${RELEASE} data/work.openpaper.Paperwork.appdata.xml
endif

release_pypi: download_data
	@echo "Releasing paperwork-gtk (paperwork) ..."
	${PYTHON} ./setup.py sdist
	twine upload dist/paperwork-${RELEASE}.tar.gz
	@echo "All done"

clean:
	rm -f ${VERSION_FILE}
	rm -rf build dist src/*.egg-info
	$(MAKE) -C src/paperwork_gtk/model/help clean
	$(MAKE) -C src/paperwork_gtk/icon clean

# PIP_ARGS is used by Flatpak build
install_py: ${VERSION_FILE} l10n_compile
	${PYTHON} ./setup.py install ${PIP_ARGS}

install_c:

uninstall_py:
	pip3 uninstall -y paperwork

uninstall_c:

l10n_extract:
	$(CURDIR)/../tools/l10n_extract.sh "$(CURDIR)/src" "$(CURDIR)/l10n"
	$(MAKE) -C src/paperwork_gtk/model/help l10n_extract

l10n_compile:
	$(CURDIR)/../tools/l10n_compile.sh \
		"$(CURDIR)/l10n" \
		"$(CURDIR)/src/paperwork_gtk/l10n" \
		"paperwork_gtk"

help:
	@echo "make build || make build_py"
	@echo "make check"
	@echo "make help: display this message"
	@echo "make install || make install_py"
	@echo "make uninstall || make uninstall_py"
	@echo "make release || make release_pypi"

.PHONY: \
	build \
	build_c \
	build_py \
	check \
	doc \
	exe \
	help \
	install \
	install_c \
	install_py \
	l10n_extract \
	release \
	release_pypi \
	test \
	uninstall \
	uninstall_c \
	version
