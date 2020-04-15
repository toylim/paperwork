TEX=data/intro.tex
OUT_LATEX=data/intro.aux data/intro.log
OUT_PDF=out/intro.pdf

all: $(OUT_PDF)

out/paperwork_going_up.png: data/paperwork_going_up.svg
	inkscape -z $< -e $@

$(OUT_PDF): $(TEX) out/paperwork_going_up.png
	pdflatex --output-directory=out ../$<

clean:
	rm -f $(OUT_PNG)
	rm -f $(OUT_PDF)
	rm -f $(OUT_LATEX)

.PHONY: clean
