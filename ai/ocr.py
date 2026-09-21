import re
import os
from datetime import datetime

# Try importing pytesseract / PIL
try:
    from PIL import Image
    import pytesseract
    _TESSERACT_AVAILABLE = True
except Exception:
    _TESSERACT_AVAILABLE = False

def extract_text_from_file(file_path: str) -> str:
    """Extracts raw text from image or text-based receipt."""
    if not file_path or not os.path.exists(file_path):
        return ""
    
    ext = os.path.splitext(file_path)[1].lower()
    
    if ext in ('.txt', '.csv', '.json', '.log'):
        try:
            with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                return f.read()
        except Exception:
            return ""

    if ext in ('.png', '.jpg', '.jpeg', '.bmp', '.tiff', '.webp'):
        if _TESSERACT_AVAILABLE:
            try:
                img = Image.open(file_path)
                return pytesseract.image_to_string(img)
            except Exception:
                pass

    return ""

def parse_receipt_data(text: str, fallback_vendor: str = "Vendor", fallback_amount: float = 0.0) -> dict:
    """
    Extracts amount, date, and vendor from receipt text using regex pattern matching.
    """
    result = {
        'amount': fallback_amount,
        'date': datetime.now().date().strftime('%Y-%m-%d'),
        'vendor': fallback_vendor,
        'raw_text': text or ''
    }

    if not text:
        return result

    # 1. Extract Amount (matches $123.45, USD 50.00, INR 1200, Total: 450.00, etc.)
    amount_patterns = [
        r'(?:total|amount|due|subtotal|balance|grand\s*total)[\s:]*[$€£₹]?\s*([0-9]+(?:[.,][0-9]{2})?)',
        r'[$€£₹]\s*([0-9]+(?:[.,][0-9]{2})?)',
        r'([0-9]+(?:[.,][0-9]{2}))\s*(?:usd|eur|gbp|inr)',
        r'\b([0-9]+\.[0-9]{2})\b'
    ]
    for pattern in amount_patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            try:
                raw_amt = match.group(1).replace(',', '')
                val = float(raw_amt)
                if 0.5 <= val <= 500000.0:
                    result['amount'] = val
                    break
            except Exception:
                continue

    # 2. Extract Date (matches YYYY-MM-DD, DD/MM/YYYY, MM/DD/YYYY, MMM DD YYYY)
    date_patterns = [
        r'\b(20\d{2}[-/][01]\d[-/][0-3]\d)\b',
        r'\b([0-3]?\d[-/][01]?\d[-/]20\d{2})\b',
        r'\b((?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\s+[0-3]?\d,?\s+20\d{2})\b'
    ]
    for pattern in date_patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            date_str = match.group(1)
            # Try formatting
            for fmt in ('%Y-%m-%d', '%Y/%m/%d', '%d-%m-%Y', '%d/%m/%Y', '%m/%d/%Y', '%B %d, %Y', '%b %d, %Y', '%B %d %Y'):
                try:
                    dt = datetime.strptime(date_str, fmt)
                    result['date'] = dt.date().strftime('%Y-%m-%d')
                    break
                except Exception:
                    pass
            break

    # 3. Extract Vendor (first non-empty line or known keyword)
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    if lines:
        for line in lines[:3]:
            # Clean up line
            cleaned = re.sub(r'[^a-zA-Z0-9\s&.-]', '', line).strip()
            if len(cleaned) >= 3 and not any(k in cleaned.lower() for k in ['receipt', 'invoice', 'tax', 'bill', 'date', 'total']):
                result['vendor'] = cleaned[:60]
                break

    return result
