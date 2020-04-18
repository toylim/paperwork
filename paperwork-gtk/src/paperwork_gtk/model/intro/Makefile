TEX=data/intro.tex
OUT_LATEX=data/intro.aux data/intro.log
OUT_PDF=out/intro.pdf

all: $(OUT_PDF)

out/paperwork_going_up.png: data/paperwork_going_up.svg
	inkscape -z $< -e $@

screenshots:
	LANG=C WAYLAND_DISPLAY= xvfb-run sh ./screenshot.sh

$(OUT_PDF): $(TEX) screenshots out/paperwork_going_up.png
	pdflatex --output-directory=out ../$<

clean:
	rm -f $(OUT_PNG)
	rm -f $(OUT_PDF)
	rm -f $(OUT_LATEX)

data: $(OUT_PDF)

upload_data:

.PHONY: clean screenshots data upload_data
