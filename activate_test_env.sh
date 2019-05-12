if ! [ -e sub/libinsane/Makefile ] ; then
	git submodule init
	git submodule update --recursive --remote --init
fi

make venv
source venv/bin/activate
cd sub/libinsane && source ./activate_test_env.sh ; cd ../..
