# order matters (dependencies)
ALL_COMPONENTS = \
	openpaperwork-core \
	openpaperwork-gtk \
	paperwork-backend \
	paperwork-shell \
	paperwork-gtk

build:


openpaperwork-core_install_py:
	echo "Installing openpaperwork-core"
	$(MAKE) -C openpaperwork-core install_py

%_install_py: openpaperwork-core_install_py
	echo "Installing $(@:%_install_py=%)"
	$(MAKE) -C $(@:%_install_py=%) install_py


clean: $(ALL_COMPONENTS:%=%_clean)
	rm -rf build dist
	rm -rf venv
	rm -f data.tar.gz
	make -C sub/libinsane clean || true
	make -C sub/libpillowfight clean || true
	make -C sub/pyocr clean || true

install_py: download_data $(ALL_COMPONENTS:%=%_install_py)

install: install_py

uninstall: $(ALL_COMPONENTS:%=%_uninstall)

uninstall_py: $(ALL_COMPONENTS:%=%_uninstall_py)

uninstall_c: $(ALL_COMPONENTS:%=%_uninstall_c)

version: $(ALL_COMPONENTS:%=%_version)

check: $(ALL_COMPONENTS:%=%_check)

test: $(ALL_COMPONENTS:%=%_test)

data: $(ALL_COMPONENTS:%=%_data)

upload_data: data
	tar -cvzf data.tar.gz \
		paperwork-gtk/src/paperwork_gtk/model/help/out/*.pdf \
		paperwork-gtk/src/paperwork_gtk/icon/*.png \
	ci/deliver_data.sh data.tar.gz

data.tar.gz:
	ci/download_data.sh data.tar.gz

download_data: data.tar.gz
	tar -xvzf data.tar.gz

doc: $(ALL_COMPONENTS:%=%_doc)

upload_doc: $(ALL_COMPONENTS:%=%_upload_doc)

release_pypi: download_data l10n_compile $(ALL_COMPONENTS:%=%_release_pypi)

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

windows_exe:
	# dirty hack to make cx_freeze happy
	# Cx_freeze looks for a file sqlite3.dll whereas in MSYS2, it's called
	# libsqlite3-0.dll
	mkdir -p /mingw32/DLLs
	cp /mingw32/bin/libsqlite3-0.dll /mingw32/DLLs/sqlite3.dll

	rm -rf $(CURDIR)/build/exe
	$(MAKE) $(ALL_COMPONENTS:%=%_windows_exe)

	# a bunch of things are missing
	mkdir -p $(CURDIR)/build/exe/lib
	cp -Ra /mingw32/lib/gdk-pixbuf-2.0 $(CURDIR)/build/exe/lib
	# 2nd part of the dirty hack to make cx_freeze happy
	rm -f $(CURDIR)/build/exe/lib/sqlite3.dll

	mkdir -p $(CURDIR)/build/exe/share
	cp -Ra /mingw32/share/icons $(CURDIR)/build/exe/share
	cp -Ra /mingw32/share/locale $(CURDIR)/build/exe/share
	cp -Ra /mingw32/share/themes $(CURDIR)/build/exe/share
	cp -Ra /mingw32/share/fontconfig $(CURDIR)/build/exe/share
	cp -Ra /mingw32/share/poppler $(CURDIR)/build/exe/share
	cp -Ra /mingw32/share/glib-2.0 $(CURDIR)/build/exe/share

	mkdir -p dist
	(cd $(CURDIR)/build/exe ; zip -r ../../dist/paperwork.zip *)

l10n_extract: $(ALL_COMPONENTS:%=%_l10n_extract)

l10n_compile: $(ALL_COMPONENTS:%=%_l10n_compile)

help:
	@echo "make build: run 'python3 ./setup.py build' in all components"
	@echo "make clean"
	@echo "make help: display this message"
	@echo "make install : run 'python3 ./setup.py install' on all components"
	@echo "make release"
	@echo "make uninstall : run 'pip3 uninstall -y (component)' on all components"
	@echo "make l10n_extract"
	@echo "make l10n_compile"
	@echo "Components:" ${ALL_COMPONENTS}

%_version:
	echo "Making version file $(@:%_version=%)"
	$(MAKE) -C $(@:%_version=%) version

%_check:
	echo "Checking $(@:%_check=%)"
	$(MAKE) -C $(@:%_check=%) check

%_test:
	echo "Testing $(@:%_test=%)"
	$(MAKE) -C $(@:%_test=%) test

%_upload_doc:
	echo "Uploading doc of $(@:%_upload_doc=%)"
	$(MAKE) -C $(@:%_upload_doc=%) upload_doc

%_doc:
	echo "Generating doc of $(@:%_doc=%)"
	$(MAKE) -C $(@:%_doc=%) doc

%_data:
	echo "Generating data files of $(@:%_data=%)"
	$(MAKE) -C $(@:%_data=%) data

%_clean:
	echo "Cleaning $(@:%_clean=%)"
	$(MAKE) -C $(@:%_clean=%) clean

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

%_windows_exe: version download_data libinsane_win32 pyocr_win32 libpillowfight_win32
	echo "Building Windows exe for $(@:%_windows_exe=%)"
	$(MAKE) -C $(@:%_windows_exe=%) windows_exe

%_l10n_extract:
	echo "Extracting translatable strings from $(@:%_l10n_extract=%)"
	$(MAKE) -C $(@:%_l10n_extract=%) l10n_extract

%_l10n_compile:
	echo "Compiling translated strings for $(@:%_l10n_compile=%)"
	$(MAKE) -C $(@:%_l10n_compile=%) l10n_compile

venv:
	echo "Building virtual env"
	make -C sub/libinsane build_c
	virtualenv -p python3 --system-site-packages venv

.PHONY: help build clean test check install install_py install_c uninstall \
	uninstall_c uninstall_py release release_pypi libinsane_win32 \
	pyocr_win32 libpillowfight_win32 doc upload_doc data upload_data \
	download_data l10n_extract l10n_compile
