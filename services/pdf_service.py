from xhtml2pdf import pisa
import io
import markdown2

class PDFService:
    @staticmethod
    def create_content_pdf(title, content_markdown):
        # Convert Markdown to HTML
        # Using 'extras' to support tables and better list handling
        html_body = markdown2.markdown(content_markdown, extras=["tables", "fenced-code-blocks", "break-on-newline"])
        
        # Modern, professional HTML template for educators
        html_content = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="UTF-8">
            <style>
                @page {{
                    size: a4;
                    margin: 2.5cm;
                    @frame footer {{
                        -pdf-frame-content: footerContent;
                        bottom: 1.5cm;
                        margin-left: 2.5cm;
                        margin-right: 2.5cm;
                        height: 1cm;
                    }}
                }}
                
                body {{
                    font-family: Helvetica, Arial, sans-serif;
                    font-size: 11pt;
                    line-height: 1.6;
                    color: #2d3748;
                }}
                
                .header {{
                    text-align: center;
                    border-bottom: 2px solid #10b981;
                    padding-bottom: 20px;
                    margin-bottom: 30px;
                }}
                
                .brand {{
                    color: #10b981;
                    font-size: 9pt;
                    font-weight: bold;
                    text-transform: uppercase;
                    letter-spacing: 1px;
                    margin-bottom: 5px;
                }}
                
                h1 {{
                    color: #1a202c;
                    font-size: 24pt;
                    margin: 0;
                    line-height: 1.2;
                }}
                
                h2 {{
                    color: #059669;
                    font-size: 16pt;
                    border-bottom: 1px solid #e2e8f0;
                    padding-bottom: 5px;
                    margin-top: 25px;
                    margin-bottom: 15px;
                }}
                
                h3 {{
                    color: #374151;
                    font-size: 13pt;
                    margin-top: 20px;
                    margin-bottom: 10px;
                }}
                
                p {{
                    margin-bottom: 12px;
                }}
                
                ul, ol {{
                    margin-bottom: 15px;
                    padding-left: 20px;
                }}
                
                li {{
                    margin-bottom: 5px;
                }}
                
                strong {{
                    color: #111827;
                }}
                
                table {{
                    width: 100%;
                    border-collapse: collapse;
                    margin-bottom: 20px;
                }}
                
                th, td {{
                    border: 1px solid #e2e8f0;
                    padding: 10px;
                    text-align: left;
                }}
                
                th {{
                    background-color: #f8fafc;
                    color: #475569;
                    font-weight: bold;
                }}
                
                .footer {{
                    text-align: center;
                    font-size: 9pt;
                    color: #94a3b8;
                    padding-top: 10px;
                }}
            </style>
        </head>
        <body>
            <div class="header">
                <div class="brand">TeachShare AI Intelligence</div>
                <h1>{title}</h1>
            </div>
            
            <div class="content">
                {html_body}
            </div>
            
            <div id="footerContent" class="footer">
                Powered by DeepSeek V3 • Created with TeachShare
            </div>
        </body>
        </html>
        """
        
        result = io.BytesIO()
        pisa_status = pisa.CreatePDF(
            io.BytesIO(html_content.encode("utf-8")),
            dest=result
        )
        
        if pisa_status.err:
            print(f"XHTML2PDF Error: {pisa_status.err}")
            raise Exception("Failed to generate professional PDF")
            
        return result.getvalue()
