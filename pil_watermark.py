import io
import math

from PIL import Image  # Pillow >= 8.0.0
from PIL import ImageDraw
from fitz import fitz  # pymupdf >= 1.18.13

anchor_dict = {'lt': 'la', 'mt': 'ma', 'rt': 'ra',
               'lm': 'lm', 'mm': 'mm', 'rm': 'rm',
               'lb': 'ld', 'mb': 'md', 'rb': 'rd'}
align_dict = {'l': 'left', 'm': 'center', 'r': 'right'}


def rgba_to_stream(image_byte):
    # create two sub-images: (1) the base-image, (2) the mask image (alpha values).
    pix = fitz.Pixmap(image_byte)  # intermediate pixmap
    base = fitz.Pixmap(pix, 0)  # extract base image without alpha
    mask = fitz.Pixmap(None, pix)  # extract alpha channel for the mask image
    basestream = base.pil_tobytes("JPEG")
    maskstream = mask.pil_tobytes("JPEG")

    return basestream, maskstream


class TextWatermark:
    _watermark_text = ''
    _rect_size = (0, 0)
    _rotate_specs = None
    _txt_specs = None
    _repeated = None
    _wtm_im = None

    # txt_specs: dictionary with key 'pos', 'color_rgba', 'font', 'align', 'anchor'
    # repeated: None or dictionary with key 'spacing_w', 'spacing_h'

    def __init__(self, watermark_txt, rect_size, txt_specs, rotate_angle=0, repeated=None, pos='lt'):
        img_w, img_h = rect_size[0], rect_size[1]
        self._watermark_text = watermark_txt
        self._rotate_specs = {'angle': rotate_angle, 'ori_rect': rect_size}
        self._repeated = repeated
        self._txt_specs = txt_specs
        if rotate_angle in [0, 180]:
            self._rect_size = rect_size
        elif rotate_angle in [-90, 90]:
            self._rect_size = (img_h, img_w)
        else:
            self._rect_size = (int(img_w * math.cos(math.radians(rotate_angle)) +
                                   img_h * math.sin(math.radians(rotate_angle))),
                               int(img_h * math.cos(math.radians(rotate_angle)) +
                                   img_w * math.sin(math.radians(rotate_angle))))
        self.position_process(pos)

    def position_process(self, pos):
        rect_w, rect_h = self._rect_size[0], self._rect_size[1]
        txt_pos_w_dict = {'l': 0, 'm': rect_w // 2, 'r': rect_w}
        txt_pos_h_dict = {'t': 0, 'm': rect_h // 2, 'b': rect_h}
        anchor = anchor_dict[pos]
        align = align_dict[pos[0]]
        txt_pos_w = txt_pos_w_dict[pos[0]]
        txt_pos_h = txt_pos_h_dict[pos[1]]
        self._txt_specs['anchor'] = anchor
        self._txt_specs['align'] = align
        self._txt_specs['pos'] = (txt_pos_w, txt_pos_h)

    def generate_text_single(self):
        wtm_im = Image.new('RGBA', self._rect_size, (255, 255, 255, 0))

        draw = ImageDraw.Draw(wtm_im)

        draw.text(self._txt_specs['pos'],
                  self._watermark_text,
                  fill=self._txt_specs['color_rgba'],
                  font=self._txt_specs['font'],
                  anchor=self._txt_specs['anchor'],
                  align=self._txt_specs['align'])

        self._wtm_im = wtm_im

    def generate_text_repeated(self):
        wtm_im = Image.new('RGBA', self._rect_size, (255, 255, 255, 0))

        draw = ImageDraw.Draw(wtm_im)

        txt_w, txt_h = draw.textsize(self._watermark_text, font=self._txt_specs['font'])

        spacing_w = txt_w * (1 + self._repeated['spacing_w'])
        spacing_h = txt_h * (1 + self._repeated['spacing_h'])
        # print(spacing_w, spacing_h)

        # add repeated watermark
        for i in range(int(self._rect_size[0] // spacing_w) + 1):
            for j in range(int(self._rect_size[1] // spacing_h) + 1):
                draw.text(((i + 0.15) * spacing_w,  # not on the edge
                           j * spacing_h),
                          self._watermark_text,
                          fill=self._txt_specs['color_rgba'],
                          font=self._txt_specs['font'],
                          align=self._txt_specs['align'])

        self._wtm_im = wtm_im

    def generate_text(self):
        if self._repeated:
            self.generate_text_repeated()
        else:
            self.generate_text_single()

    def rotate_crop(self):
        wtm_im = self._wtm_im
        if self._rotate_specs['angle'] == 180:
            wtm_im = wtm_im.rotate(self._rotate_specs['angle'], expand=1)
        elif self._rotate_specs['angle'] in [-90, 90]:
            wtm_im = wtm_im.rotate(self._rotate_specs['angle'], expand=1)
        else:
            rotate_im = wtm_im.rotate(self._rotate_specs['angle'], expand=1)
            crop_img_w_border = int(self._rotate_specs['ori_rect'][1] *
                                    math.cos(math.radians(self._rotate_specs['angle'])) *
                                    math.sin(math.radians(self._rotate_specs['angle'])))
            crop_img_h_border = int(self._rotate_specs['ori_rect'][0] *
                                    math.cos(math.radians(self._rotate_specs['angle'])) *
                                    math.sin(math.radians(self._rotate_specs['angle'])))
            wtm_im = rotate_im.crop((crop_img_w_border,
                                     crop_img_h_border,
                                     crop_img_w_border + self._rotate_specs['ori_rect'][0],
                                     crop_img_h_border + self._rotate_specs['ori_rect'][1]))
        self._wtm_im = wtm_im

    def generate_im(self):
        self.generate_text()
        if self._rotate_specs['angle'] != 0:
            self.rotate_crop()
        return self._wtm_im

    def get_size(self):
        return self._rect_size


class WatermarkStack:
    _rect_size = (0, 0)
    _lst_wtm = []

    def __init__(self, rect_size):
        self._rect_size = rect_size
        self._lst_wtm = []

    def add_watermark(self, wtm):
        if wtm.get_size() != self._rect_size:
            print('watermark_size_error')
            return
        self._lst_wtm.append(wtm)

    def generate_wtm_im(self):
        stack_im = Image.new('RGBA', self._rect_size, (255, 255, 255, 0))
        for wtm in self._lst_wtm:
            wtm_im = wtm.generate_im()
            stack_im = Image.alpha_composite(stack_im, wtm_im)

        buf = io.BytesIO()
        stack_im.save(buf, format='PNG')
        byte_im = buf.getvalue()

        return byte_im

    def generate_wtm_stream(self):
        watermark_byte = self.generate_wtm_im()
        return rgba_to_stream(watermark_byte)
