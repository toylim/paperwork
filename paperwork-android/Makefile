VERSION_FILE = src/paperwork_android/_version.py

all: android

version: ${VERSION_FILE}

${VERSION_FILE}:
	echo -n "version = \"" >| $@
	echo -n $(shell git describe --always) >> $@
	$(eval branch_name = $(shell git symbolic-ref HEAD 2>/dev/null))
	if [ -n "${branch_name}" ] && [ "${branch_name}" != "refs/heads/master" ] ; then echo -n "-${branch_name}" >> $@ ; fi
	echo "\"" >> $@

android: ${VERSION_FILE}
	pip3 install buildozer
	pip3 install cython
	buildozer ${BUILDOZER_ARGS} android debug

android_run: android
	buildozer ${BUILDOZER_ARGS} android deploy run logcat

clean:
	# Keep in mind that buildozer may not be installed when the developer
	# is working on the desktop version of Paperwork only
	buildozer ${BUILDOZER_ARGS} android clean || true

check:
	flake8 --exclude=_version.py src/paperwork_android

test:


.PHONY: all android android_run version check test
