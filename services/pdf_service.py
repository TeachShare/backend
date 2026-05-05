from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, ListFlowable, ListItem, HRFlowable
from reportlab.lib import colors
from reportlab.lib.units import cm
from reportlab.lib.enums import TA_CENTER, TA_LEFT
import io
import re

class PDFService:
    @staticmethod
    def create_content_pdf(title, content_markdown):
        buffer = io.BytesIO()
        
        # Define Document Template
        doc = SimpleDocTemplate(
            buffer,
            pagesize=A4,
            rightMargin=2.0*cm,
            leftMargin=2.0*cm,
            topMargin=2.5*cm,
            bottomMargin=2.5*cm
        )
        
        # Define Styles
        styles = getSampleStyleSheet()
        
        style_brand = ParagraphStyle(
            'Brand',
            parent=styles['Normal'],
            fontName='Helvetica-Bold',
            fontSize=9,
            textColor=colors.HexColor('#10b981'),
            alignment=TA_CENTER,
            spaceAfter=2,
            leading=12,
            textTransform='uppercase',
            letterSpacing=1
        )
        
        style_title = ParagraphStyle(
            'MainTitle',
            parent=styles['Heading1'],
            fontName='Helvetica-Bold',
            fontSize=22,
            textColor=colors.HexColor('#1a202c'),
            alignment=TA_CENTER,
            spaceAfter=20,
            leading=26
        )
        
        style_h2 = ParagraphStyle(
            'Heading2',
            parent=styles['Heading2'],
            fontName='Helvetica-Bold',
            fontSize=15,
            textColor=colors.HexColor('#059669'),
            spaceBefore=12,
            spaceAfter=6,
            leading=18,
            textTransform='uppercase'
        )
        
        style_h3 = ParagraphStyle(
            'Heading3',
            parent=styles['Heading3'],
            fontName='Helvetica-Bold',
            fontSize=12,
            textColor=colors.HexColor('#374151'),
            spaceBefore=10,
            spaceAfter=6,
            leading=14
        )
        
        style_body = ParagraphStyle(
            'BodyText',
            parent=styles['Normal'],
            fontName='Helvetica',
            fontSize=10.5,
            textColor=colors.HexColor('#2d3748'),
            leading=15,
            spaceAfter=8
        )

        # Parse Markdown to Flowables
        flowables = []
        
        # Header (Brand + Title)
        flowables.append(Paragraph("TeachShare AI Intelligence", style_brand))
        flowables.append(Paragraph(title, style_title))
        flowables.append(HRFlowable(width="100%", thickness=1, color=colors.HexColor('#e2e8f0'), spaceAfter=20))
        
        # Process Content
        lines = content_markdown.split('\n')
        current_list = []
        
        def flush_list():
            if current_list:
                flowables.append(ListFlowable(
                    [ListItem(Paragraph(li, style_body), leftIndent=20, spaceBefore=2) for li in current_list],
                    bulletType='bullet',
                    start='•',
                    leftIndent=20,
                    bulletOffsetY=0
                ))
                current_list.clear()
                flowables.append(Spacer(1, 0.2*cm))

        for line in lines:
            line = line.strip()
            if not line:
                flush_list()
                continue
            
            # Markdown Heading 2
            if line.startswith('## '):
                flush_list()
                text = line[3:].strip()
                flowables.append(Spacer(1, 0.3*cm))
                flowables.append(Paragraph(text, style_h2))
                flowables.append(HRFlowable(width="30%", thickness=1.5, color=colors.HexColor('#10b981'), hAlign='LEFT', spaceAfter=10))
                continue
            
            # Markdown Heading 3
            if line.startswith('### '):
                flush_list()
                text = line[4:].strip()
                flowables.append(Paragraph(text, style_h3))
                continue

            # Bullet Points
            bullet_match = re.match(r'^[\*\-\+]\s+(.*)', line)
            if bullet_match:
                text = bullet_match.group(1)
                text = re.sub(r'\*\*(.*?)\*\*', r'<b>\1</b>', text)
                text = re.sub(r'\*(.*?)\*', r'<i>\1</i>', text)
                current_list.append(text)
                continue
            
            # Numbered Lists
            num_list_match = re.match(r'^\d+\.\s+(.*)', line)
            if num_list_match:
                text = num_list_match.group(1)
                text = re.sub(r'\*\*(.*?)\*\*', r'<b>\1</b>', text)
                text = re.sub(r'\*(.*?)\*', r'<i>\1</i>', text)
                current_list.append(text)
                continue

            # Regular Paragraph
            flush_list()
            text = line
            text = re.sub(r'\*\*(.*?)\*\*', r'<b>\1</b>', text)
            text = re.sub(r'\*(.*?)\*', r'<i>\1</i>', text)
            flowables.append(Paragraph(text, style_body))

        flush_list()

        # Footer Drawing
        def add_footer(canvas, doc):
            canvas.saveState()
            canvas.setStrokeColor(colors.HexColor('#e2e8f0'))
            canvas.line(2*cm, 2*cm, A4[0]-2*cm, 2*cm)
            canvas.setFont('Helvetica', 8)
            canvas.setFillColor(colors.HexColor('#94a3b8'))
            footer_text = "Generated by TeachShare AI • DeepSeek V3 Engine • Page %d" % doc.page
            canvas.drawCentredString(A4[0]/2, 1.5*cm, footer_text)
            canvas.restoreState()

        # Build PDF
        doc.build(flowables, onFirstPage=add_footer, onLaterPages=add_footer)
        
        pdf_content = buffer.getvalue()
        buffer.close()
        return pdf_content
