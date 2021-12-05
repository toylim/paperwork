AUTHORS.git.json:
	$(CURDIR)/../../../../tools/get_git_authors.py $(CURDIR)/../../../.. >| $(CURDIR)/AUTHORS.git.json

AUTHORS.json: \
		../../../../AUTHORS.ui.json \
		AUTHORS.git.json
	$(CURDIR)/../../../../tools/merge_authors_json.py $^ \
		>| $(CURDIR)/AUTHORS.json

data:
	$(MAKE) clean
	$(MAKE) AUTHORS.json

clean:
	rm -f $(CURDIR)/AUTHORS.git.json
	rm -f $(CURDIR)/AUTHORS.json

.PHONY: clean data
