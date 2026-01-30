from server.tools.pdf_generator import generate_pdf_report

markdown_test = """
# Test PDF

Ini adalah percobaan generate PDF dari markdown.

- Satu
- Dua
- Tiga

**Bold** dan _italic_.
"""

result = generate_pdf_report.invoke({"markdown_content": markdown_test, "filename": "test_output.pdf"})
print(result)
