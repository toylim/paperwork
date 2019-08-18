# order matters (dependencies)
ALL_COMPONENTS = paperwork-backend paperwork-gtk

build: $(ALL_COMPONENTS:%=%_build)

clean: $(ALL_COMPONENTS:%=%_clean)
	rm -rf build dist
	rm -rf venv
	make -C sub/libinsane clean || true
	make -C sub/libpillowfight clean || true
	make -C sub/pyocr clean || true

install: $(ALL_COMPONENTS:%=%_install)

install_py: $(ALL_COMPONENTS:%=%_install_py)

install_c: $(ALL_COMPONENTS:%=%_install_c)

uninstall: $(ALL_COMPONENTS:%=%_uninstall)

uninstall_py: $(ALL_COMPONENTS:%=%_uninstall_py)

uninstall_c: $(ALL_COMPONENTS:%=%_uninstall_c)

version: $(ALL_COMPONENTS:%=%_version)

check: $(ALL_COMPONENTS:%=%_check)

test: $(ALL_COMPONENTS:%=%_test)

doc: $(ALL_COMPONENTS:%=%_doc)

release_pypi: $(ALL_COMPONENTS:%=%_release_pypi)

release: $(ALL_COMPONENTS:%=%_release)
ifeq (${RELEASE}, )
	@echo "You must specify a release version (make release RELEASE=1.2.3)"
else
	@echo "Will release: ${RELEASE}"
	git tag -a ${RELEASE} -m ${RELEASE}
	git push origin ${RELEASE}
	make clean
	make version
	make release_pypi
	@echo "All done"
	@echo "IMPORTANT: Don't forgot to add the latest release on Flathub !"
endif

linux_exe: $(ALL_COMPONENTS:%=%_linux_exe)

libinsane_win32:
	${MAKE} -C sub/libinsane install PREFIX=/mingw32

pyocr_win32:
	${MAKE} -C sub/pyocr install

libpillowfight_win32:
	${MAKE} -C sub/libpillowfight install_py

windows_exe: $(ALL_COMPONENTS:%=%_windows_exe)
	mkdir -p dist
	(cd build/exe ; zip -r ../../dist/paperwork.zip *)

help:
	@echo "make build: run 'python3 ./setup.py build' in all components"
	@echo "make clean"
	@echo "make help: display this message"
	@echo "make install : run 'python3 ./setup.py install' on all components"
	@echo "make release"
	@echo "make uninstall : run 'pip3 uninstall -y (component)' on all components"
	@echo "Components:" ${ALL_COMPONENTS}

%_version:
	echo "Making version file $(@:%_version=%)"
	$(MAKE) -C $(@:%_version=%) version

%_check:
	echo "Checking $(@:%_check=%)"
	$(MAKE) -C $(@:%_check=%) check

%_test:
	echo "Checking $(@:%_test=%)"
	$(MAKE) -C $(@:%_test=%) test

%_doc:
	echo "Checking $(@:%_doc=%)"
	$(MAKE) -C $(@:%_doc=%) doc

%_build:
	echo "Building $(@:%_build=%)"
	$(MAKE) -C $(@:%_build=%) build

%_clean:
	echo "Building $(@:%_clean=%)"
	$(MAKE) -C $(@:%_clean=%) clean

%_install:
	echo "Installing $(@:%_install=%)"
	$(MAKE) -C $(@:%_install=%) install

%_build_py:
	echo "Building $(@:%_build_py=%)"
	$(MAKE) -C $(@:%_build=%) build_py

%_install_py:
	echo "Installing $(@:%_install_py=%)"
	$(MAKE) -C $(@:%_build=%) install_py

%_build_c:
	echo "Building $(@:%_build_c=%)"
	$(MAKE) -C $(@:%_build=%) build_c

%_install_c:
	echo "Installing $(@:%_install_c=%)"
	$(MAKE) -C $(@:%_build=%) install_c

%_uninstall:
	echo "Uninstalling $(@:%_uninstall=%)"
	$(MAKE) -C $(@:%_uninstall=%) uninstall

%_uninstall_py:
	echo "Uninstalling $(@:%_uninstall_py=%)"
	$(MAKE) -C $(@:%_uninstall=%) uninstall_py

%_uninstall_c:
	echo "Uninstalling $(@:%_uninstall_c=%)"
	$(MAKE) -C $(@:%_uninstall=%) uninstall_c

%_release:
	echo "Releasing $(@:%_release=%)"
	$(MAKE) -C $(@:%_release=%) release

%_release_pypi:
	echo "Releasing $(@:%_release_pypi=%)"
	$(MAKE) -C $(@:%_release_pypi=%) release_pypi

%_linux_exe:
	echo "Building Linux exe for $(@:%_linux_exe=%)"
	$(MAKE) -C $(@:%_linux_exe=%) linux_exe

%_windows_exe: version libinsane_win32 pyocr_win32 libpillowfight_win32
	echo "Building Windows exe for $(@:%_windows_exe=%)"
	$(MAKE) -C $(@:%_windows_exe=%) windows_exe

venv:
	echo "Building virtual env"
	git submodule init
	git submodule update --recursive --remote --init
	make -C sub/libinsane build_c
	virtualenv -p python3 --system-site-packages venv

.PHONY: help build clean test check install install_py install_c uninstall \
	uninstall_c uninstall_py release libinsane_win32 pyocr_win32 \
	libpillowfight_win32
