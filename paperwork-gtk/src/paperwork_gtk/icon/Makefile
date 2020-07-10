all: data

out/paperwork_%.png: data/paperwork.svg
	convert -background None $(CURDIR)/$< -resize $*x$* $(CURDIR)/$@

data: \
	out/paperwork_16.png \
	out/paperwork_32.png \
	out/paperwork_48.png \
	out/paperwork_64.png \
	out/paperwork_128.png

clean:
	rm -f $(CURDIR)/out/*.png

.PHONY: all data clean
