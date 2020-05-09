all: data

out/paperwork_%.png: data/paperwork.svg
	convert -background None $(CURDIR)/$< -resize $*x$* $(CURDIR)/$@

data: \
	out/paperwork_128.png

clean:
	rm -f $(CURDIR)/out/*.png

.PHONY: all data clean
