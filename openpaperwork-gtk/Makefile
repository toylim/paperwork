VERSION_FILE = src/openpaperwork_gtk/_version.py
PYTHON ?= python3

build: build_c build_py

install: install_py install_c

uninstall: uninstall_py

build_py: ${VERSION_FILE}
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
	cd .. && ./ci/deliver_doc.sh ${CURDIR}/doc/_build/html openpaperwork_gtk

check:
	flake8 src/openpaperwork_gtk

test: install
	python3 -m unittest discover --verbose -s tests

linux_exe:

windows_exe:
	${PYTHON} /mingw32/bin/pip3-script.py install .

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
	${PYTHON} ./setup.py sdist upload
	@echo "All done"

clean:
	rm -rf doc/_build
	rm -f ${VERSION_FILE}
	rm -rf build dist *.egg-info

# PIP_ARGS is used by Flatpak build
install_py: ${VERSION_FILE}
	${PYTHON} ./setup.py install ${PIP_ARGS}

install_c:

uninstall_py:
	pip3 uninstall -y paperwork-backend

uninstall_c:

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
	doc \
	exe \
	help \
	install \
	install_c \
	install_py \
	release \
	test \
	uninstall \
	uninstall_c \
	version