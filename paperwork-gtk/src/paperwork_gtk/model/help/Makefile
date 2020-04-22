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

data: $(OUT_PDF)

upload_data: $(OUT_PDF)
	cd $(CURDIR)/../../../../.. && ci/deliver_data.sh $(CURDIR)/$< help

.PHONY: clean screenshots data upload_data
