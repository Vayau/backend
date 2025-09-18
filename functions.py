import os
import mimetypes
from docx2pdf import convert
from PIL import Image
from fpdf import FPDF
import pdfkit
import subprocess
import cv2
import pytesseract
from transformers import TrOCRProcessor, VisionEncoderDecoderModel
import re
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.cidfonts import UnicodeCIDFont
from reportlab.lib.pagesizes import A4
from PyPDF2 import PdfReader
from deep_translator import GoogleTranslator

def convert_to_pdf(input_path: str, output_path: str) -> None:
    mime_type, _ = mimetypes.guess_type(input_path)
    if mime_type is None:
        raise ValueError("Cannot determine file type.")

    # DOCX
    if mime_type == 'application/vnd.openxmlformats-officedocument.wordprocessingml.document':
        convert(input_path, output_path)

    # XLSX
    elif mime_type == 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet':
        try:
            subprocess.run(['xlsx2pdf', input_path, output_path], check=True)
        except Exception as e:
            raise RuntimeError(f"Failed to convert XLSX to PDF: {e}")

    # Image
    elif mime_type.startswith('image/'):
        image = Image.open(input_path)
        image.save(output_path, "PDF", resolution=100.0)

    # TXT
    elif mime_type == 'text/plain':
        with open(input_path, 'r', encoding='utf-8') as f:
            text = f.read()
        pdf = FPDF()
        pdf.add_page()
        pdf.set_auto_page_break(auto=True, margin=15)
        pdf.set_font("Arial", size=12)
        for line in text.split('\n'):
            pdf.cell(200, 10, txt=line, ln=True)
        pdf.output(output_path)

    # HTML
    elif mime_type == 'text/html':
        pdfkit.from_file(input_path, output_path)

    else:
        raise ValueError(f"Unsupported file type: {mime_type}")

class HandwrittenOCR:
    def __init__(self, tesseract_path: str = r"C:\\Program Files\\Tesseract-OCR\\tesseract.exe"):
        pytesseract.pytesseract.tesseract_cmd = tesseract_path

        self.processor = TrOCRProcessor.from_pretrained("microsoft/trocr-base-handwritten")
        self.model = VisionEncoderDecoderModel.from_pretrained("microsoft/trocr-base-handwritten")

    def _recognize_english(self, img_crop):
        pixel_values = self.processor(images=img_crop, return_tensors="pt").pixel_values
        generated_ids = self.model.generate(pixel_values)
        return self.processor.batch_decode(generated_ids, skip_special_tokens=True)[0]

    def _recognize_malayalam(self, img_crop):
        return pytesseract.image_to_string(img_crop, lang="mal")

    def _contains_malayalam(self, text):
        return bool(re.search(r'[\u0D00-\u0D7F]', text))

    def process_image(self, image_path: str) -> str:
        image = cv2.imread(image_path)
        image_rgb = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
        pil_img = Image.fromarray(image_rgb)

        text_en = self._recognize_english(pil_img).strip()
        text_ml = self._recognize_malayalam(pil_img).strip()

        if text_ml and self._contains_malayalam(text_ml):
            return text_ml
        elif text_en:
            return text_en
        else:
            return text_en if len(text_en) >= len(text_ml) else text_ml

    def save_to_pdf(self, text: str, output_path: str = "ocr_output.pdf") -> None:
        pdfmetrics.registerFont(UnicodeCIDFont("HeiseiMin-W3"))
        doc = SimpleDocTemplate(output_path, pagesize=A4)
        styles = getSampleStyleSheet()
        custom_style = ParagraphStyle("Custom", parent=styles["Normal"], fontName="HeiseiMin-W3", fontSize=12)

        flowables = [Paragraph(text, custom_style)]
        doc.build(flowables)

    def process_and_save(self, image_path: str, output_path: str = "ocr_output.pdf") -> str:
        text = self.process_image(image_path)
        self.save_to_pdf(text, output_path)
        return text

class PDFTranslator:
    def __init__(self, chunk_size: int = 4500):
        self.chunk_size = chunk_size

    def extract_text_from_pdf(self, pdf_path: str) -> str:
        reader = PdfReader(pdf_path)
        text = ""
        for page in reader.pages:
            page_text = page.extract_text()
            if page_text:
                text += page_text + "\n"
        return text

    def _protect_links(self, text: str):
        link_pattern = re.compile(r"(https?://\S+|www\.\S+|[\w\.-]+@[\w\.-]+\.\w+)")
        links = {}
        def replacer(match):
            placeholder = f"§§LINK{len(links)}§§"
            links[placeholder] = match.group(0)
            return placeholder
        protected_text = link_pattern.sub(replacer, text)
        return protected_text, links

    def _restore_links(self, text: str, links: dict) -> str:
        for placeholder, link in links.items():
            pattern = re.compile(re.escape(placeholder), re.IGNORECASE)
            link_markup = f'<a href="{link}" color="blue"><u>{link}</u></a>'
            text = pattern.sub(link_markup, text)
        return text

    def translate_text(self, text: str, src_lang: str, dest_lang: str) -> str:
        protected_text, links = self._protect_links(text)
        lines = protected_text.splitlines()
        translated_lines = []
        current_chunk = ""
        for line in lines:
            if len(current_chunk) + len(line) + 1 > self.chunk_size:
                translated_chunk = GoogleTranslator(source=src_lang, target=dest_lang).translate(current_chunk)
                translated_lines.append(translated_chunk)
                current_chunk = ""
            current_chunk += line + "\n"
        if current_chunk.strip():
            translated_chunk = GoogleTranslator(source=src_lang, target=dest_lang).translate(current_chunk)
            translated_lines.append(translated_chunk)

        translated_text = "\n".join(translated_lines)
        return self._restore_links(translated_text, links)

    def write_text_to_pdf(self, text: str, output_pdf_path: str):
        pdfmetrics.registerFont(UnicodeCIDFont('HeiseiMin-W3'))
        doc = SimpleDocTemplate(output_pdf_path, pagesize=A4,
                                rightMargin=40, leftMargin=40,
                                topMargin=50, bottomMargin=50)
        styles = getSampleStyleSheet()
        normal_style = ParagraphStyle(
            "Normal",
            parent=styles["Normal"],
            fontName="HeiseiMin-W3",
            fontSize=12,
            leading=16,
        )
        story = []
        for line in text.splitlines():
            if line.strip():
                story.append(Paragraph(line, normal_style))
                story.append(Spacer(1, 6))
            else:
                story.append(Spacer(1, 12))
        doc.build(story)

    def translate_pdf(self, input_pdf: str, output_pdf: str, direction: str) -> str:
        text = self.extract_text_from_pdf(input_pdf)
        if direction == 'ml2en':
            translated = self.translate_text(text, src_lang='ml', dest_lang='en')
        elif direction == 'en2ml':
            translated = self.translate_text(text, src_lang='en', dest_lang='ml')
        else:
            raise ValueError("Invalid direction. Use 'ml2en' or 'en2ml'.")
        self.write_text_to_pdf(translated, output_pdf)
        return translated

