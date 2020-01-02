import sys

from . import pdf


DOC_GENERATORS = {
    'pdf': pdf.generate,
    # 'img': img.generate,
    # 'pdf_img': pdf_img.generate,
}


def main_generate_one():
    if len(sys.argv) <= 2:
        print("Usage:")
        print("  {} <type> <out_file>".format(sys.argv[0]))
        sys.exit(1)
    DOC_GENERATORS[sys.argv[1]](sys.argv[2])
