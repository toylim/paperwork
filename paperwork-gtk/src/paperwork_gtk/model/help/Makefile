TEX=data/intro.tex
OUT_LATEX=data/intro.aux data/intro.log
OUT_PDF=out/intro.pdf

all: $(OUT_PDF)

out/paperwork_going_up.png: data/paperwork_going_up.svg
	convert $< $@

screenshots:
	[ -f $(CURDIR)/${OUT_PDF} ] || LANG=C WAYLAND_DISPLAY= xvfb-run sh ./screenshot.sh

$(OUT_PDF): $(TEX) screenshots out/paperwork_going_up.png
	pdflatex --output-directory=out ../$<

clean:
	rm -f $(CURDIR)/out/*.png
	rm -f $(CURDIR)/$(OUT_PDF)
	rm -f $(CURDIR)/$(OUT_LATEX)

data:
	rm -f $(OUT_PDF)
	$(MAKE) $(OUT_PDF)

.PHONY: clean screenshots data
