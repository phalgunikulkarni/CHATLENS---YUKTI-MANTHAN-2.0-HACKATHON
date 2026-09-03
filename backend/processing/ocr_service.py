import easyocr

class OCRService:
    def __init__(self):
        # Using english only for MVP to keep it lightweight
        self.reader = easyocr.Reader(['en'], gpu=False)

    def extract_text(self, image_path: str) -> str | None:
        try:
            results = self.reader.readtext(image_path, detail=0)
            if not results:
                return None
            return " ".join(results)
        except Exception as e:
            print(f"OCR Error: {e}")
            return None

ocr_service = OCRService()
