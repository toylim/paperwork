#!/usr/bin/bash

#   Needed:
# flatpak install --user https://builder.openpaper.work/paperwork_master.flatpakref
# flatpak install --user paperwork-origin work.openpaper.Paperwork.Debug//master
# flatpak install --user https://builder.openpaper.work/paperwork_testing.flatpakref
# flatpak install --user paperwork-origin work.openpaper.Paperwork.Debug//testing
# flatpak install --user https://builder.openpaper.work/paperwork_develop.flatpakref
# flatpak install --user paperwork-origin work.openpaper.Paperwork.Debug//develop

#   The stack trace file must contain something similar to:
# /app/lib/libinsane.so.1(+0x1aa14)[0x7f2ad73b5a14]
# /usr/lib/x86_64-linux-gnu/libc.so.6(+0x39690)[0x7f2adf6e7690]
# /usr/lib/x86_64-linux-gnu/libc.so.6(+0x9cc2a)[0x7f2adf74ac2a]
# /usr/lib/x86_64-linux-gnu/libc.so.6(+0x6a716)[0x7f2adf718716]
# /usr/lib/x86_64-linux-gnu/libc.so.6(+0x7c78a)[0x7f2adf72a78a]
# /app/lib/libinsane.so.1(lis_log+0x125)[0x7f2ad73a3fb5]
# /app/lib/libinsane.so.1(+0x1b7ba)[0x7f2ad73b67ba]
# /app/lib/libinsane.so.1(+0x1b9f8)[0x7f2ad73b69f8]
# /app/lib/libinsane.so.1(lis_worker_main+0x23a)[0x7f2ad73b6c6a]
# /app/lib/libinsane.so.1(lis_api_workaround_dedicated_process+0x3a8)[0x7f2ad73b4518]
# /app/lib/libinsane.so.1(lis_safebet+0x1b2)[0x7f2ad73ab502]
# /app/lib/libinsane_gobject.so.1(libinsane_api_new_safebet+0x5a)[0x7f2ad766cf5a]
# /usr/lib/x86_64-linux-gnu/libffi.so.6(ffi_call_unix64+0x4c)[0x7f2ade490b78]
# /usr/lib/x86_64-linux-gnu/libffi.so.6(ffi_call+0x1d4)[0x7f2ade490374]
# /usr/lib/python3.7/site-packages/gi/_gi.cpython-37m-x86_64-linux-gnu.so(+0x2a12d)[0x7f2addfdf12d]


if [ $# -lt 2 ] ; then
	echo "Syntax:"
	echo "  $0 <stack trace file> <number of Flatpak commits to examine>"
	exit 1
fi

stacktrace_file="$1"
nb_commits="$2"

for branch in master testing develop ; do
	for commit in $(flatpak remote-info \
			--log -c paperwork-origin \
			work.openpaper.Paperwork//${branch} \
			| head -n ${nb_commits}) ; do

		echo "==================================="
		echo "Branch: ${branch}"
		echo "Flatpak Commit: ${commit}"
		echo

		for line in $(< ${stacktrace_file}) ; do
			if [ -z "${line}" ] || [ "${line}" = "-" ] ; then
				echo "(...)"
				echo
				continue
			fi

			filename=$(echo "${line}"|cut -d'(' -f1)
			addr=$(echo "${line}"|cut -d'(' -f2|cut -d')' -f1)
			result=$(flatpak run --devel --command=addr2line \
				work.openpaper.Paperwork//${branch} \
				-i -p -f -e "${filename}" "${addr}")
			echo "IN: ${filename}(${addr})"
			echo "ADDR2LINE: ${result}"
			echo
		done

		echo
		echo
	done
done
