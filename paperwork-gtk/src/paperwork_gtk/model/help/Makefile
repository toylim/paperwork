IN_INTRO_TEX=data/intro.tex
OUT_INTRO_PDF=out/intro.pdf
IN_USAGE_TEX=data/usage.tex
OUT_USAGE_PDF=out/usage.pdf

all: data

out/paperwork_going_up.png: data/paperwork_going_up.svg
	convert $< $@

screenshots:
	[ -f $(CURDIR)/${OUT_INTRO_PDF} ] || LANG=C WAYLAND_DISPLAY= xvfb-run sh ./screenshot.sh

$(OUT_INTRO_PDF): $(IN_INTRO_TEX) screenshots out/paperwork_going_up.png
	pdflatex --output-directory=out ../$<

$(OUT_USAGE_PDF): $(IN_USAGE_TEX) screenshots out/paperwork_going_up.png
	# run pdflatex twice because of the TOC
	pdflatex --output-directory=out ../$<
	pdflatex --output-directory=out ../$<

clean:
	rm -f $(CURDIR)/out/*.png
	rm -f $(CURDIR)/$(OUT_INTRO_PDF)
	rm -f $(CURDIR)/data/*.aux $(CURDIR)/data/*.log

data:
	rm -f out/*.pdf
	rm -f out/*.toc
	$(MAKE) $(OUT_INTRO_PDF) $(OUT_USAGE_PDF)

.PHONY: all clean screenshots data
