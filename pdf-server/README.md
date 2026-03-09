# שרת מילוי טופס 101

## קבצים נדרשים
- `server.py` — השרת הראשי
- `fields_template_final.json` — תבנית שדות הטופס
- `tofes-101.pdf` — הטופס הרשמי המקורי
- `fill_pdf_form_with_annotations.py` — סקריפט המילוי

## העלאה ל-Railway

1. צור repository ב-GitHub עם כל הקבצים
2. היכנס ל-railway.app
3. New Project → Deploy from GitHub repo
4. בחר את ה-repo

## API

### GET /health
בדיקת תקינות

### POST /fill
מקבל JSON עם נתוני הטופס, מחזיר PDF ב-base64

#### דוגמה:
```json
{
  "taxYear": 2025,
  "idNum": "123456789",
  "lastName": "כהן",
  "firstName": "ישראל",
  "birthDate": "01/01/1990",
  "gender": "M",
  "status": "NASUY",
  "phone": "050-1234567",
  "email": "israel@example.com",
  "street": "הרצל 1",
  "city": "תל אביב",
  "resident": "YES",
  "kupat": "מכבי",
  "kibbutz": "NO",
  "startThisYear": "01/03/2025",
  "incomeType": "MONTH",
  "otherIncome": "NONE",
  "taxCoord": "NO_INCOME",
  "signDate": "10/03/2025",
  "exemptions": {
    "resident": false,
    "army": true,
    "armyStart": "01/03/2022",
    "armyEnd": "01/03/2025"
  },
  "children": [],
  "spouse": null
}
```

#### תגובה:
```json
{
  "pdf": "base64encodedPDF..."
}
```
