VERSION_FILE = src/paperwork_backend/_version.py
PYTHON ?= python3

build: build_c build_py

install: install_py install_c

uninstall: uninstall_py

build_py: ${VERSION_FILE} l10n_compile
	${PYTHON} ./setup.py build

build_c:

version: ${VERSION_FILE}

${VERSION_FILE}:
	echo -n "version = \"" >| $@
	echo -n $(shell git describe --always) >> $@
	echo "\"" >> $@

doc: install_py
	$(MAKE) -C doc html

doc/_build/html/index.html: doc

upload_doc: doc/_build/html/index.html
	cd .. && ./ci/deliver_doc.sh ${CURDIR}/doc/_build/html paperwork_backend

data:

check:
	flake8 src/paperwork_backend

test: install
	python3 -m unittest discover --verbose -s tests

linux_exe:

windows_exe:
	${PYTHON} /mingw32/bin/pip3-script.py install .
	# ugly, but "import pkg_resources" doesn't work in frozen environments
	# and I don't want to have to patch the build machine to fix it every
	# time.
	mkdir -p $(CURDIR)/../build/exe/data
	(cd $(CURDIR)/src && find . -name '*.mo' -exec cp --parents \{\} $(CURDIR)/../build/exe/data \; )

release:
ifeq (${RELEASE}, )
	@echo "You must specify a release version (make release RELEASE=1.2.3)"
else
	@echo "Will release: ${RELEASE}"
	@echo "Checking release is in ChangeLog ..."
	grep ${RELEASE} ChangeLog | grep -v "/xx"
endif

release_pypi:
	@echo "Releasing paperwork-backend ..."
	${PYTHON} ./setup.py sdist
	twine upload dist/paperwork-backend-${RELEASE}.tar.gz
	@echo "All done"

clean:
	rm -f ${VERSION_FILE}
	rm -rf build dist *.egg-info

# PIP_ARGS is used by Flatpak build
install_py: ${VERSION_FILE} l10n_compile
	${PYTHON} ./setup.py install ${PIP_ARGS}

install_c:

uninstall_py:
	pip3 uninstall -y paperwork-backend

uninstall_c:

l10n_extract:
	$(CURDIR)/../tools/l10n_extract.sh "$(CURDIR)/src" "$(CURDIR)/l10n"

l10n_compile:
	$(CURDIR)/../tools/l10n_compile.sh \
		"$(CURDIR)/l10n" \
		"$(CURDIR)/src/paperwork_backend/l10n" \
		"paperwork_backend"

help:
	@echo "make build || make build_py"
	@echo "make check"
	@echo "make help: display this message"
	@echo "make install || make install_py"
	@echo "make uninstall || make uninstall_py"
	@echo "make release"

.PHONY: \
	build \
	build_c \
	build_py \
	check \
	data \
	doc \
	exe \
	help \
	install \
	install_c \
	install_py \
	l10n_compile \
	l10n_extract \
	release \
	test \
	upload_data \
	upload_doc \
	uninstall \
	uninstall_c \
	version
