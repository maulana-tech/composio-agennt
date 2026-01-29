import os
from server.tools.pdf_generator import generate_pdf_report

markdown_test = """
# Berita Panas Pemerintah

Berikut adalah ringkasan berita terbaru mengenai pemerintah:

## Sektor Pendidikan
- Peningkatan anggaran pendidikan sebesar 20%.
- Program beasiswa baru untuk mahasiswa berprestasi.

## Kebijakan Ekonomi
| Kebijakan | Dampak |
|---|---|
| Penurunan Pajak | Meningkatkan daya beli |
| Subsidi BBM | Menjaga stabilitas harga |

**Penting:** Laporan ini dibuat secara otomatis.
"""

result = generate_pdf_report.invoke({"markdown_content": markdown_test, "filename": "test_output.pdf"})
print(result)
