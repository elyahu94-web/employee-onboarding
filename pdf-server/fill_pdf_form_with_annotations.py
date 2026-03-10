"""
fill_pdf_form_with_annotations.py
ממלא טופס PDF עם תמיכה מלאה בעברית
משתמש ב-reportlab לציור טקסט + pypdf למיזוג
"""
import json
import sys
import os
from io import BytesIO

from pypdf import PdfReader, PdfWriter
from reportlab.pdfgen import canvas
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont


def get_hebrew_font():
    font_paths = [
        '/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf',
        '/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf',
        '/usr/share/fonts/truetype/freefont/FreeSans.ttf',
        '/usr/share/fonts/truetype/noto/NotoSansHebrew-Regular.ttf',
        '/usr/share/fonts/truetype/noto/NotoSans-Regular.ttf',
        os.path.join(os.path.dirname(os.path.abspath(__file__)), 'NotoSansHebrew-Regular.ttf'),
        os.path.join(os.path.dirname(os.path.abspath(__file__)), 'DejaVuSans.ttf'),
    ]
    for p in font_paths:
        if os.path.exists(p):
            return p
    return None


def reverse_hebrew(text):
    try:
        from bidi.algorithm import get_display
        return get_display(text)
    except ImportError:
        pass
    return text[::-1]


def transform_from_image_coords(bbox, image_width, image_height, pdf_width, pdf_height):
    x_scale = pdf_width / image_width
    y_scale = pdf_height / image_height
    left   = bbox[0] * x_scale
    right  = bbox[2] * x_scale
    top    = pdf_height - (bbox[1] * y_scale)
    bottom = pdf_height - (bbox[3] * y_scale)
    return left, bottom, right, top


def transform_from_pdf_coords(bbox, pdf_height):
    left   = bbox[0]
    right  = bbox[2]
    top    = pdf_height - bbox[1]
    bottom = pdf_height - bbox[3]
    return left, bottom, right, top


def fill_pdf_form(input_pdf_path, fields_json_path, output_pdf_path):
    with open(fields_json_path, 'r', encoding='utf-8') as f:
        fields_data = json.load(f)

    reader = PdfReader(input_pdf_path)

    pdf_dimensions = {}
    for i, page in enumerate(reader.pages):
        mb = page.mediabox
        pdf_dimensions[i + 1] = (float(mb.width), float(mb.height))

    font_name = 'Helvetica'
    font_path = get_hebrew_font()
    if font_path:
        try:
            pdfmetrics.registerFont(TTFont('HebrewFont', font_path))
            font_name = 'HebrewFont'
            print(f"Using font: {font_path}")
        except Exception as e:
            print(f"Font error: {e}")

    fields_by_page = {}
    for field in fields_data['form_fields']:
        p = field['page_number']
        if p not in fields_by_page:
            fields_by_page[p] = []
        fields_by_page[p].append(field)

    overlays = {}
    for page_num, fields in fields_by_page.items():
        pdf_width, pdf_height = pdf_dimensions[page_num]
        packet = BytesIO()
        c = canvas.Canvas(packet, pagesize=(pdf_width, pdf_height))
        page_info = next(p for p in fields_data['pages'] if p['page_number'] == page_num)

        for field in fields:
            if 'entry_text' not in field or 'text' not in field['entry_text']:
                continue
            text = field['entry_text']['text']
            if not text:
                continue

            font_size = field['entry_text'].get('font_size', 7)

            if 'pdf_width' in page_info:
                left, bottom, right, top = transform_from_pdf_coords(
                    field['entry_bounding_box'], pdf_height)
            else:
                left, bottom, right, top = transform_from_image_coords(
                    field['entry_bounding_box'],
                    page_info['image_width'], page_info['image_height'],
                    pdf_width, pdf_height)

            box_h = top - bottom
            display_text = reverse_hebrew(text)
            c.setFont(font_name, font_size)
            text_y = bottom + (box_h - font_size * 0.7) / 2
            c.drawRightString(right - 1, text_y, display_text)

        c.save()
        packet.seek(0)
        overlays[page_num] = packet

    writer = PdfWriter()
    for i, page in enumerate(reader.pages):
        page_num = i + 1
        if page_num in overlays:
            overlay_reader = PdfReader(overlays[page_num])
            page.merge_page(overlay_reader.pages[0])
        writer.add_page(page)

    with open(output_pdf_path, 'wb') as f:
        writer.write(f)

    print(f"Done: {output_pdf_path}")


if __name__ == '__main__':
    if len(sys.argv) != 4:
        print("Usage: fill_pdf_form_with_annotations.py [input pdf] [fields.json] [output pdf]")
        sys.exit(1)
    fill_pdf_form(sys.argv[1], sys.argv[2], sys.argv[3])
