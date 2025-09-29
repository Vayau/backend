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
import spacy
from spacy.matcher import Matcher
import pdfplumber
from collections import defaultdict
import torch
from pdf2image import convert_from_path

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

    def process_pdf(self, pdf_path: str) -> str:
        images = convert_from_path(pdf_path, dpi=200)
        full_text = []

        for page_num, pil_img in enumerate(images, start=1):
            pil_img = pil_img.convert("RGB")

            text_en = self._recognize_english(pil_img).strip()
            text_ml = self._recognize_malayalam(pil_img).strip()

            if text_ml and self._contains_malayalam(text_ml):
                chosen_text = text_ml
            elif text_en:
                chosen_text = text_en
            else:
                chosen_text = text_en if len(text_en) >= len(text_ml) else text_ml

            full_text.append(f"--- Page {page_num} ---\n{chosen_text}\n")

        return "\n".join(full_text)
    
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
        from reportlab.lib.colors import black
        from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
        from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer
        from reportlab.lib.pagesizes import A4
        from reportlab.pdfbase import pdfmetrics
        from reportlab.pdfbase.ttfonts import TTFont
        import os
        
        doc = SimpleDocTemplate(output_pdf_path, pagesize=A4,
                                rightMargin=40, leftMargin=40,
                                topMargin=50, bottomMargin=50)
        styles = getSampleStyleSheet()
        
        # Try to register Malayalam font if available, otherwise use default
        font_name = "Helvetica"  # Default font
        try:
            # Check if Malayalam font is available - use absolute path
            malayalam_font_path = os.path.abspath("NotoSansMalayalam-Regular.ttf")
            if os.path.exists(malayalam_font_path):
                # Register the font with a unique name
                pdfmetrics.registerFont(TTFont('NotoSansMalayalam', malayalam_font_path))
                font_name = "NotoSansMalayalam"
                print(f"Using Malayalam font: {font_name} from {malayalam_font_path}")
                
                # Test if the font is properly registered
                try:
                    test_style = ParagraphStyle("Test", fontName=font_name, fontSize=12)
                    print(f"Font registration successful: {font_name}")
                except Exception as test_e:
                    print(f"Font test failed: {test_e}, falling back to Helvetica")
                    font_name = "Helvetica"
            else:
                print(f"Malayalam font not found at {malayalam_font_path}, using Helvetica")
        except Exception as e:
            print(f"Could not register Malayalam font: {e}, using Helvetica")
            font_name = "Helvetica"
        
        # Create a style with black text color and appropriate font
        normal_style = ParagraphStyle(
            "Normal",
            parent=styles["Normal"],
            fontName=font_name,
            fontSize=12,
            leading=16,
            textColor=black,  # Ensure text is black
            spaceAfter=6,
            alignment=0,  # Left alignment
        )
        
        story = []
        for line in text.splitlines():
            if line.strip():
                story.append(Paragraph(line, normal_style))
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

class DocumentClassifier:
    def __init__(self):
        self.nlp = spacy.load("en_core_web_trf")
        self.matcher = Matcher(self.nlp.vocab)
        self._add_patterns()

    def _add_patterns(self):
        # HR Patterns
        self.matcher.add("RECRUITMENT_ADV_NO", [[{"TEXT": {"REGEX": r"HR/\d{4}/\d+"}}]])
        self.matcher.add("GRADE_PAY", [[{"TEXT": {"REGEX": r"Grade\s?[A-Z0-9]+"}}]])
        self.matcher.add("JOB_TITLE", [[{"LOWER": {"IN": ["engineer", "manager", "officer", "assistant"]}}]])

        # Procurement Patterns
        self.matcher.add("TENDER_ID", [[{"TEXT": {"REGEX": r"Tender\s?No\.\s?\d+/\d+"}}]])
        self.matcher.add("PURCHASE_ORDER_NO", [[{"TEXT": {"REGEX": r"PO\s?\d{3,}"}}]])
        self.matcher.add("CONTRACT_ID", [[{"TEXT": {"REGEX": r"Contract\s?No\.\s?\w+"}}]])

        # Legal Patterns
        self.matcher.add("CASE_NO", [[{"TEXT": {"REGEX": r"(W\.P\.|C\.R\.|O\.S\.)\s?\d+/\d+"}}]])
        self.matcher.add("COURT_NAME", [[{"LOWER": {"IN": ["supreme", "high", "district", "tribunal"]}}]])
        self.matcher.add("LAW_SECTION", [[{"TEXT": {"REGEX": r"(Section|Article)\s?\d+[A-Za-z]?"}}]])

    def extract_metadata(self, text):
        doc = self.nlp(text)
        matches = self.matcher(doc)

        metadata = {
            "general": {"PERSON": [], "ORG": [], "DATE": [], "AMOUNT": [], "LOCATION": []},
            "HR": {"EMPLOYEE_ID": [], "JOB_TITLE": [], "GRADE_PAY": [], "RECRUITMENT_ADV_NO": []},
            "Procurement": {"TENDER_ID": [], "PURCHASE_ORDER_NO": [], "BIDDER_NAME": [], "CONTRACT_ID": [], "ITEM_SERVICE": [], "DEADLINE": []},
            "Legal": {"CASE_NO": [], "COURT_NAME": [], "LAW_SECTION": [], "PARTY_NAME": [], "SOP_CLAUSE": []},
        }

        for ent in doc.ents:
            if ent.label_ in metadata["general"]:
                metadata["general"][ent.label_].append(ent.text)

        for match_id, start, end in matches:
            label = self.nlp.vocab.strings[match_id]
            span = doc[start:end].text
            for dept in metadata:
                if label in metadata[dept]:
                    metadata[dept][label].append(span)

        return metadata

    def classify_department(self, metadata, full_text=""):
        text = (full_text or "").lower()
        raw = defaultdict(float)
        reasons = defaultdict(list)

        # Procurement logic
        proc_matches = (
            len(metadata["Procurement"]["TENDER_ID"])
            + len(metadata["Procurement"]["PURCHASE_ORDER_NO"])
            + len(metadata["Procurement"]["CONTRACT_ID"])
        )
        procurement_phrases = [
            "tender document", "notice inviting tender", "form of tender",
            "bill of quantities", "tender security", "tenderer", "earnest money",
            "emd", "bid", "bidder", "purchase order", "contract no",
            "evaluation of tender", "tender opening", "tender validity"
        ]
        proc_kw_hits = sum(1 for kw in procurement_phrases if kw in text)

        if proc_matches:
            raw["Procurement"] += proc_matches * 3.0
            reasons["Procurement"].append(f"explicit_proc_matches={proc_matches}")
        if proc_kw_hits:
            raw["Procurement"] += proc_kw_hits * 1.2
            reasons["Procurement"].append(f"procurement_phrase_hits={proc_kw_hits}")
        if any(k in text for k in ["notice inviting tender", "form of tender", "bill of quantities"]):
            raw["Procurement"] += 3.0
            reasons["Procurement"].append("strong_proc_indicator_phrase")

        # HR
        if metadata["HR"]["RECRUITMENT_ADV_NO"]:
            raw["HR"] += 3.0
            reasons["HR"].append("RECRUITMENT_ADV_NO")
        if metadata["HR"]["JOB_TITLE"]:
            raw["HR"] += len(metadata["HR"]["JOB_TITLE"]) * 1.0
            reasons["HR"].append("JOB_TITLE_found")
        if metadata["HR"]["GRADE_PAY"]:
            raw["HR"] += 1.0
            reasons["HR"].append("GRADE_PAY_found")

        # Legal
        if metadata["Legal"]["CASE_NO"]:
            raw["Legal"] += len(metadata["Legal"]["CASE_NO"]) * 3.0
            reasons["Legal"].append("CASE_NO_found")
        if metadata["Legal"]["COURT_NAME"]:
            raw["Legal"] += len(metadata["Legal"]["COURT_NAME"]) * 0.8
            reasons["Legal"].append("COURT_NAME_found")
        if metadata["Legal"]["LAW_SECTION"]:
            raw["Legal"] += len(metadata["Legal"]["LAW_SECTION"]) * 0.6
            reasons["Legal"].append("LAW_SECTION_found")

        legal_phrases = ["petitioner", "respondent", "writ petition", "tribunal order", "appeal", "arbitration clause"]
        legal_phrase_hits = sum(1 for k in legal_phrases if k in text)
        if legal_phrase_hits:
            raw["Legal"] += legal_phrase_hits * 0.8
            reasons["Legal"].append(f"legal_phrase_hits={legal_phrase_hits}")

        # Finance
        if "tax reimbursement" in text or "tax return" in text or "tax refund" in text:
            raw["Finance"] += 3.0
            reasons["Finance"].append("tax_term_found")
        if "annual report" in text or "balance sheet" in text or "audited" in text:
            raw["Finance"] += 2.0
            reasons["Finance"].append("financial_statement_found")
        if "invoice" in text:
            raw["Finance"] += 1.5
            reasons["Finance"].append("invoice_found")
        if "profit and loss" in text or "p&l account" in text:
            raw["Finance"] += 2.0
            reasons["Finance"].append("p&l_found")
        if "budget estimate" in text or "expenditure report" in text:
            raw["Finance"] += 1.5
            reasons["Finance"].append("budget_terms_found")

        # Regulatory
        if "eia" in text or "environmental impact" in text or "environmental clearance" in text:
            raw["Regulatory"] += 3.0
            reasons["Regulatory"].append("environmental_found")
        if "safety directive" in text or "safety norms" in text:
            raw["Regulatory"] += 1.5
            reasons["Regulatory"].append("safety_directive_found")
        if "compliance order" in text or "regulatory directive" in text:
            raw["Regulatory"] += 2.0
            reasons["Regulatory"].append("regulatory_directive_found")

        # Engineering
        if "rolling stock" in text or "maximo" in text:
            raw["Engineering"] += 3.0
            reasons["Engineering"].append("rolling_stock_or_maximo")
        if "technical specification" in text or "engineering report" in text:
            raw["Engineering"] += 1.5
            reasons["Engineering"].append("technical_terms_found")

        # Dominance/Suppression
        if raw["Procurement"] >= 3.0:
            raw["Procurement"] += 3.0
            reasons["Procurement"].append("procurement_strong_flag")
            for dept in ["Legal", "Finance", "Regulatory", "Engineering", "HR"]:
                if raw[dept] < 3.0:
                    raw[dept] *= 0.35
                    reasons[dept].append("suppressed_by_procurement")

        if raw["Finance"] >= 3.0:
            raw["Finance"] += 3.0
            reasons["Finance"].append("finance_strong_flag")
            for dept in ["Legal", "Procurement", "Regulatory", "Engineering", "HR"]:
                if raw[dept] < 3.0:
                    raw[dept] *= 0.35
                    reasons[dept].append("suppressed_by_finance")

        if raw["Legal"] >= 3.0:
            raw["Legal"] += 3.0
            reasons["Legal"].append("legal_strong_flag")
            for dept in ["Finance", "Procurement", "Regulatory", "Engineering", "HR"]:
                if raw[dept] < 3.0:
                    raw[dept] *= 0.35
                    reasons[dept].append("suppressed_by_legal")

        # Normalize scores
        max_raw = max(raw.values()) if raw else 1.0
        normalized = {dept: round(val / max_raw, 2) for dept, val in raw.items()}

        # Departments above threshold
        predicted_departments = [dept for dept, score in normalized.items() if score >= 0.5]

        # Print details (stays in functions.py)
        print("\nScores:")
        for dept, score in normalized.items():
            print(f"  {dept}: {score}")
        print("\nReasons:")
        for dept, rlist in reasons.items():
            if rlist:
                print(f"  {dept}: {rlist}")
        print("\nPredicted Departments:", predicted_departments)

        return predicted_departments

    def extract_text_from_pdf(self, pdf_path):
        text = ""
        with pdfplumber.open(pdf_path) as pdf:
            for page in pdf.pages:
                page_text = page.extract_text()
                if page_text:
                    text += page_text + "\n"
        return text

    def process_pdf(self, pdf_path):
        text = self.extract_text_from_pdf(pdf_path)
        metadata = self.extract_metadata(text)
        predicted = self.classify_department(metadata, full_text=text)
        return metadata, predicted