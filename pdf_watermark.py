import glob
import os
from concurrent import futures

import tqdm
from PIL import ImageFont
from fitz import fitz  # pymupdf >= 1.18.13

from pil_watermark import WatermarkStack, TextWatermark


def email_watermark(email, rect_size):
    email_wtm_stack = WatermarkStack(rect_size)

    txt_size = 80
    fnt = ImageFont.truetype("Pillow/Tests/fonts/FreeMono.ttf", txt_size)
    rotate_angle = 30

    wtm_1 = TextWatermark(email,
                          rect_size,
                          txt_specs={'color_rgba': (0, 0, 0, 48),
                                     'font': fnt},
                          rotate_angle=rotate_angle,
                          repeated={'spacing_w': 0.5,
                                    'spacing_h': 6})

    email_wtm_stack.add_watermark(wtm_1)

    # header
    header = 'Please keep this document for personal use only\nDO NOT DISTRIBUTE IT'
    wtm_2 = TextWatermark(header,
                          rect_size,
                          txt_specs={'color_rgba': (0, 0, 0, 48),
                                     'font': fnt},
                          pos='rt')

    email_wtm_stack.add_watermark(wtm_2)

    return email_wtm_stack


def add_watermark_to_pdf(src_pdf, tgt_pdf, email):
    doc = fitz.open(src_pdf)
    dict_xref = {}

    for pg in doc:
        pg_size = pg.mediabox_size
        str_pg_size = '{}x{}'.format(pg_size[0], pg_size[1])
        rect = pg.mediabox

        if str_pg_size in dict_xref:
            pg.insertImage(rect, xref=dict_xref[str_pg_size])
        else:
            page_highres = (int(rect[2] * 4), int(rect[3] * 4))
            wtm_stack = email_watermark(email, page_highres)
            basestream, maskstream = wtm_stack.generate_wtm_stream()
            dict_xref[str_pg_size] = pg.insert_image(rect, stream=basestream, mask=maskstream)

    doc.save(tgt_pdf)


def watermark_folder(email, src_folder, tgt_folder):
    src_pdfs = glob.glob('{}/*.pdf'.format(src_folder))

    # use userid to create subfolder storing each person's pdfs
    userid = email.split('@')[0]
    user_path = os.path.join(tgt_folder, userid)
    os.makedirs(user_path, exist_ok=True)

    for src_pdf in src_pdfs:
        tgt_pdf = os.path.join(user_path, os.path.basename(src_pdf))
        add_watermark_to_pdf(src_pdf, tgt_pdf, email)


def process_all_emails(emails_txt, src_folder, tgt_folder, multi=True):
    email_file = open(emails_txt, "r")
    lst_wtm = email_file.readlines()

    if multi:
        with futures.ProcessPoolExecutor() as executor:
            fs = {
                executor.submit(watermark_folder, *(wtm, src_folder, tgt_folder))
                for wtm in lst_wtm
            }
            for i, f in tqdm.tqdm(enumerate(futures.as_completed(fs)),
                                  desc="watermarks", total=len(lst_wtm)):
                f.result()
    else:
        for wtm in tqdm.tqdm(lst_wtm):
            watermark_folder(wtm, src_folder, tgt_folder)


if __name__ == "__main__":
    process_all_emails('./emails.txt', './pdf', './result')
