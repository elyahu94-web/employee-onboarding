"""
שרת Flask למילוי טופס 101
מקבל JSON מ-Apps Script, ממלא את הטופס הרשמי, מחזיר PDF
"""

import os, json, base64, copy, tempfile, subprocess, re
from flask import Flask, request, jsonify, send_file
from datetime import datetime

app = Flask(__name__)


def add_signature_to_pdf(pdf_path, sig_data_uri, output_path):
    """מצייר חתימה על עמוד 2 של ה-PDF"""
    from pypdf import PdfReader, PdfWriter
    from reportlab.pdfgen import canvas
    from reportlab.lib.utils import ImageReader
    from io import BytesIO
    from PIL import Image

    # פענח base64
    header, b64 = sig_data_uri.split(',', 1)
    img_bytes = base64.b64decode(b64)
    img = Image.open(BytesIO(img_bytes)).convert('RGBA')

    # צור PDF שכבה עם החתימה
    packet = BytesIO()
    c = canvas.Canvas(packet, pagesize=(595.275, 841.89))
    
    # קואורדינטות SIGN_SIG (עמוד 2, reportlab y מלמטה)
    sig_x, sig_y, sig_w, sig_h = 30.0, 171.9, 120.0, 35.0
    
    # שמור תמונה זמנית
    img_buffer = BytesIO()
    img.save(img_buffer, format='PNG')
    img_buffer.seek(0)
    c.drawImage(ImageReader(img_buffer), sig_x, sig_y, width=sig_w, height=sig_h, mask='auto')
    c.save()
    packet.seek(0)

    # מזג עם ה-PDF
    reader = PdfReader(pdf_path)
    writer = PdfWriter()
    overlay_reader = PdfReader(packet)

    for i, page in enumerate(reader.pages):
        if i == 1:  # עמוד 2
            page.merge_page(overlay_reader.pages[0])
        writer.add_page(page)

    with open(output_path, 'wb') as f:
        writer.write(f)
    
    return output_path

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
PDF_TEMPLATE = os.path.join(BASE_DIR, 'tofes-101.pdf')
FIELDS_TEMPLATE = os.path.join(BASE_DIR, 'fields_template_final.json')
FILL_SCRIPT = os.path.join(BASE_DIR, 'fill_pdf_form_with_annotations.py')

with open(FIELDS_TEMPLATE, encoding='utf-8') as f:
    FIELDS_TEMPLATE_DATA = json.load(f)


def fmt_date(d):
    """ממיר YYYY-MM-DD ל-DD/MM/YYYY"""
    if not d:
        return ''
    d = str(d).strip()
    if '-' in d and len(d) == 10:
        parts = d.split('-')
        if len(parts) == 3:
            return parts[2] + '/' + parts[1] + '/' + parts[0]
    return d


def build_fields_json(data: dict) -> dict:
    """ממיר נתוני טופס לפורמט fields.json לסקריפט המילוי"""
    fields = copy.deepcopy(FIELDS_TEMPLATE_DATA)

    # מיפוי placeholder -> ערך
    values = {}

    # --- עמוד 1 ---
    values['{{TAX_YEAR}}']      = str(data.get('taxYear', datetime.now().year))
    values['{{ID_NUM}}']        = data.get('idNum', '')
    values['{{LAST_NAME}}']     = data.get('lastName', '')
    values['{{FIRST_NAME}}']    = data.get('firstName', '')
    values['{{BIRTH_DATE}}']    = fmt_date(data.get('birthDate', ''))
    values['{{ALIYA_DATE}}']    = fmt_date(data.get('aliyaDate', ''))
    values['{{STREET}}']        = data.get('street', '')
    values['{{CITY}}']          = data.get('city', '')
    values['{{EMAIL}}']         = data.get('email', '')

    # טלפון — פיצול לקידומת + מספר
    phone = data.get('phone', '')
    if '-' in phone:
        parts = phone.split('-', 1)
        values['{{PHONE_PREFIX}}'] = parts[0]
        values['{{PHONE_NUMBER}}'] = parts[1]
    else:
        values['{{PHONE_PREFIX}}'] = phone[:3] if len(phone) >= 3 else phone
        values['{{PHONE_NUMBER}}'] = phone[3:]

    # קופת חולים
    kupat = data.get('kupat', '')
    values['{{KUPAT_NO}}']   = 'X' if not kupat else ''
    values['{{KUPAT_NAME}}'] = kupat if kupat else ''

    # מין
    gender = data.get('gender', '')
    values['{{GENDER_ZACHAR}}'] = 'X' if gender == 'M' else ''
    values['{{GENDER_NEKEVA}}'] = 'X' if gender == 'F' else ''

    # מצב משפחתי
    status = data.get('status', '')
    for s in ['RAVAK', 'NASUY', 'GARUSH', 'ALMAN', 'PARUD']:
        values[f'{{{{STATUS_{s}}}}}'] = 'X' if status == s else ''

    # תושב ישראל
    resident = data.get('resident', '')
    values['{{RESIDENT_YES}}'] = 'X' if resident == 'YES' else ''
    values['{{RESIDENT_NO}}']  = 'X' if resident == 'NO' else ''

    # קיבוץ
    kibbutz = data.get('kibbutz', '')
    values['{{KIBBUTZ_NO}}']   = 'X' if kibbutz == 'NO' else ''
    values['{{KIBBUTZ_YES1}}'] = 'X' if kibbutz == 'YES1' else ''
    values['{{KIBBUTZ_YES2}}'] = 'X' if kibbutz == 'YES2' else ''

    # תחילת עבודה בשנה הנוכחית
    values['{{START_THIS_YEAR}}'] = fmt_date(data.get('startThisYear', ''))

    # סוג הכנסה (ד)
    income_type = data.get('incomeType', '')
    for t in ['MONTH', 'EXTRA', 'PARTIAL', 'DAILY', 'PENSION', 'GRANT']:
        values[f'{{{{INCOME_{t}}}}}'] = 'X' if income_type == t else ''

    # הכנסות אחרות (ה)
    other = data.get('otherIncome', '')
    values['{{OTHER_NONE}}']         = 'X' if other == 'NONE' else ''
    values['{{OTHER_YES}}']          = 'X' if other == 'YES' else ''
    values['{{OTHER_CREDIT}}']       = 'X' if data.get('otherCredit') else ''
    values['{{OTHER_CREDIT_OTHER}}'] = 'X' if data.get('otherCreditOther') else ''
    values['{{OTHER_NO_KEREN}}']     = 'X' if data.get('otherNoKeren') else ''
    values['{{OTHER_NO_KITZBA}}']    = 'X' if data.get('otherNoKitzba') else ''

    other_type = data.get('otherIncomeType', '')
    for t in ['MONTH', 'EXTRA', 'PARTIAL', 'DAILY', 'PENSION', 'GRANT']:
        values[f'{{{{OTHER_TYPE_{t}}}}}'] = 'X' if other_type == t else ''

    # ג. ילדים
    children = data.get('children', [])
    for i, child in enumerate(children[:13], 1):
        values[f'{{{{CHILD{i}_NAME}}}}']    = child.get('name', '')
        values[f'{{{{CHILD{i}_ID}}}}']      = child.get('id', '')
        values[f'{{{{CHILD{i}_BIRTH}}}}']   = fmt_date(child.get('birth', ''))
        values[f'{{{{CHILD{i}_CUSTODY}}}}'] = 'X' if child.get('custody') else ''
        values[f'{{{{CHILD{i}_KITZBA}}}}']  = 'X' if child.get('kitzba') else ''

    # ו. בן/בת זוג
    spouse = data.get('spouse', {}) or {}
    values['{{SPOUSE_ID}}']       = spouse.get('id', '')
    values['{{SPOUSE_LAST}}']     = spouse.get('lastName', '')
    values['{{SPOUSE_FIRST}}']    = spouse.get('firstName', '')
    values['{{SPOUSE_BIRTH}}']    = fmt_date(spouse.get('birthDate', ''))
    values['{{SPOUSE_ALIYA}}']    = fmt_date(spouse.get('aliyaDate', ''))
    values['{{SPOUSE_PASSPORT}}'] = spouse.get('passport', '')
    values['{{SPOUSE_NO_INCOME}}']     = 'X' if spouse.get('income') == 'NO' else ''
    values['{{SPOUSE_HAS_INCOME}}']    = 'X' if spouse.get('income') == 'YES' else ''
    values['{{SPOUSE_INCOME_WORK}}']   = 'X' if spouse.get('incomeType') == 'WORK' else ''
    values['{{SPOUSE_INCOME_OTHER}}']  = 'X' if spouse.get('incomeType') == 'OTHER' else ''

    # ז. שינויים
    changes = data.get('changes', [])
    for i, ch in enumerate(changes[:3], 1):
        values[f'{{{{CHANGE{i}_DATE}}}}']    = ch.get('date', '')
        values[f'{{{{CHANGE{i}_DETAILS}}}}'] = ch.get('details', '')
        values[f'{{{{CHANGE{i}_NOTIFY}}}}']  = ch.get('notify', '')
        values[f'{{{{CHANGE{i}_SIG}}}}']     = ch.get('sig', '')

    # --- עמוד 2 ---
    # מספר זהות בעמוד 2
    values['{{ID_NUM}}'] = data.get('idNum', '')  # כבר מוגדר

    # ח. פטורים
    exemptions = data.get('exemptions', {}) or {}
    ex_map = {
        'EX_RESIDENT': 'resident',
        'EX_DISABLED_A': 'disabledA',
        'EX_DISABLED_B': 'disabledB',
        'EX_OLEH': 'oleh',
        'EX_SPOUSE': 'spouse',
        'EX_SINGLE_PAR': 'singlePar',
        'EX_CHILD_7': 'child7',
        'EX_CHILD_8': 'child8',
        'EX_SOLO_PAR': 'soloPar',
        'EX_CHILD_10': 'child10',
        'EX_CHILD_11': 'child11',
        'EX_ALIMONY': 'alimony',
        'EX_AGE1618': 'age1618',
        'EX_ARMY': 'army',
        'EX_DEGREE': 'degree',
        'EX_MILUIM': 'miluim',
    }
    for ph_key, data_key in ex_map.items():
        values[f'{{{{{ph_key}}}}}'] = 'X' if exemptions.get(data_key) else ''

    values['{{EX_OLEH_DATE}}']   = fmt_date(exemptions.get('olehDate', ''))
    values['{{EX_ARMY_START}}']  = fmt_date(exemptions.get('armyStart', ''))
    values['{{EX_ARMY_END}}']    = fmt_date(exemptions.get('armyEnd', ''))
    values['{{EX_MILUIM_DAYS}}'] = exemptions.get('miluimDays', '')

    # ט. תיאום מס
    tax_coord = data.get('taxCoord', '')
    values['{{TC_NO_INCOME}}']    = 'X' if tax_coord == 'NO_INCOME' else ''
    values['{{TC_OTHER_INCOME}}'] = 'X' if tax_coord == 'OTHER_INCOME' else ''
    values['{{TC_PEKID}}']        = 'X' if tax_coord == 'PEKID' else ''

    # טבלת תיאום מס
    tc_rows = data.get('taxCoordRows', [])
    for i, row in enumerate(tc_rows[:3], 1):
        values[f'{{{{TC_ROW{i}_EMPLOYER}}}}'] = row.get('employer', '')
        values[f'{{{{TC_ROW{i}_ADDR}}}}']     = row.get('addr', '')
        values[f'{{{{TC_ROW{i}_TIK}}}}']      = row.get('tik', '')
        values[f'{{{{TC_ROW{i}_TYPE}}}}']      = row.get('type', '')
        values[f'{{{{TC_ROW{i}_INCOME}}}}']    = row.get('income', '')
        values[f'{{{{TC_ROW{i}_TAX}}}}']       = row.get('tax', '')

    # חתימה ותאריך
    values['{{SIGN_DATE}}'] = fmt_date(data.get('signDate', ''))
    values['{{SIGN_SIG}}']  = ''  # מטופל כתמונה ב-add_signature_to_pdf

    # --- החלף placeholders בשדות ---
    for field in fields['form_fields']:
        ph = field['entry_text']['text']
        if ph in values:
            field['entry_text']['text'] = values[ph]
        else:
            field['entry_text']['text'] = ''  # ריק אם לא מוגדר

    return fields


@app.route('/health', methods=['GET'])
def health():
    return jsonify({'status': 'ok', 'version': '1.0'})


@app.route('/fill', methods=['POST'])
def fill_form():
    try:
        data = request.get_json(force=True)
        if not data:
            return jsonify({'error': 'No JSON data'}), 400

        # בנה fields.json
        fields = build_fields_json(data)

        with tempfile.TemporaryDirectory() as tmpdir:
            fields_path = os.path.join(tmpdir, 'fields.json')
            filled_path = os.path.join(tmpdir, 'filled.pdf')
            output_path = os.path.join(tmpdir, 'output.pdf')

            with open(fields_path, 'w', encoding='utf-8') as f:
                json.dump(fields, f, ensure_ascii=False)

            # הרץ סקריפט מילוי טקסט
            result = subprocess.run(
                ['python3', FILL_SCRIPT, PDF_TEMPLATE, fields_path, filled_path],
                capture_output=True, text=True
            )

            if result.returncode != 0:
                return jsonify({'error': 'Fill failed', 'details': result.stderr}), 500

            if not os.path.exists(filled_path):
                return jsonify({'error': 'Output PDF not created'}), 500

            # הוסף חתימה כתמונה אם יש
            sig_b64 = data.get('signSig', '')
            if sig_b64 and sig_b64.startswith('data:image'):
                try:
                    final_path = add_signature_to_pdf(filled_path, sig_b64, output_path)
                except Exception as e:
                    final_path = filled_path
            else:
                final_path = filled_path

            with open(final_path, 'rb') as f:
                pdf_b64 = base64.b64encode(f.read()).decode()

        return jsonify({'pdf': pdf_b64})

    except Exception as e:
        import traceback
        return jsonify({'error': str(e), 'trace': traceback.format_exc()}), 500


if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)
