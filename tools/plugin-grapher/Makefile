PYTHON ?= python3

build: build_c build_py

install: install_py install_c

uninstall: uninstall_py

build_py:
	${PYTHON} ./setup.py build

build_c:

doc:

check:
	flake8 src/paperwork_backend

test: install
	python3 -m unittest discover --verbose -s tests

linux_exe:

windows_exe:

release:

release_pypi:

clean:
	rm -rf build dist *.egg-info

install_py:
	${PYTHON} ./setup.py install ${PIP_ARGS}

install_c:

uninstall_py:
	pip3 uninstall -y plugin-grapher

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
	test \
	uninstall \
	uninstall_c \
