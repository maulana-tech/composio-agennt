# Quick Start Guide - Google Grounding

## 1. Setup (5 Menit)

### Dapatkan API Key
1. Buka [Google AI Studio](https://makersuite.google.com/app/apikey)
2. Login dengan Google Account
3. Klik "Create API Key"
4. Copy key tersebut

### Konfigurasi Environment
```bash
cd gmail-agent

# Edit file .env
nano .env

# Tambahkan:
GOOGLE_API_KEY=your-copied-api-key-here
```

### Install Dependencies
```bash
pip install -r requirements.txt
```

## 2. Testing

### Test Basic Search
```python
from google import genai
from google.genai import types

client = genai.Client(api_key="your-key")

grounding_tool = types.Tool(google_search=types.GoogleSearch())
config = types.GenerateContentConfig(tools=[grounding_tool])

response = client.models.generate_content(
    model="gemini-2.0-flash",
    contents="Who won Euro 2024?",
    config=config,
)

print(response.text)
```

**Expected Output:**
```
Spain won Euro 2024, defeating England 2-1 in the final. This victory marks Spain's record fourth European Championship title.

Sources:
[1] UEFA Official - https://...
[2] ESPN - https://...
```

## 3. Penggunaan di Agent

### Political Quotes Research
```python
# Agent akan otomatis menggunakan grounding
query = "Cari quotes Prabowo tentang pertahanan 2024"
# Gemini akan search web dan berikan jawaban dengan citations
```

### PDF Generation dengan Grounding
```python
# Generate PDF report
generate_pdf_report_wrapped(
    markdown_content="## Analisis Prabowo\n\nKonten...",
    filename="analisis_prabowo.pdf",
    enable_quote_images=True  # Generate AI images untuk quotes
)
```

## 4. Verifikasi Setup

### Cek Environment
```bash
# Cek apakah GOOGLE_API_KEY sudah set
echo $GOOGLE_API_KEY

# Cek versi google-genai
python -c "import google.genai; print(google.genai.__version__)"
```

### Test Endpoint
```bash
curl "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent" \
  -H "x-goog-api-key: $GOOGLE_API_KEY" \
  -H "Content-Type: application/json" \
  -X POST \
  -d '{
    "contents": [{"parts": [{"text": "Hello"}]}],
    "tools": [{"google_search": {}}]
  }'
```

## 5. Struktur Response

### Grounding Metadata
```json
{
  "candidates": [{
    "content": {"parts": [{"text": "Jawaban"}]},
    "groundingMetadata": {
      "webSearchQueries": ["query1", "query2"],
      "groundingChunks": [{
        "web": {
          "uri": "https://example.com",
          "title": "Title"
        }
      }]
    }
  }]
}
```

## 6. Common Issues

### Issue: "API key not valid"
**Solusi:** 
- Cek key di Google AI Studio
- Pastikan key belum expired
- Verifikasi key format (tidak ada spasi)

### Issue: "Model not found"
**Solusi:**
- Gunakan model yang kompatibel: `gemini-2.0-flash`
- Hindari model preview/experimental

### Issue: "No citations in response"
**Solusi:**
- Pastikan query memerlukan factual search
- Gemini menentukan sendiri kapan perlu search
- Cek `groundingMetadata` di response

## 7. Model yang Didukung

| Model | Grounding | Rekomendasi |
|-------|-----------|-------------|
| gemini-2.0-flash | ✅ | **Recommended** - Cepat & akurat |
| gemini-2.5-flash | ✅ | Versi terbaru |
| gemini-2.5-pro | ✅ | Kualitas tinggi, lebih lambat |
| gemini-1.5-flash | ❌ | Tidak support |

## 8. Pricing (Perkiraan)

### Gemini 3 (Current):
- ~$35-50 per 1,000 search queries
- Billing per query yang dieksekusi

### Gemini 2.5 (Legacy):
- Per prompt (flat rate)

**Tips:** 
- Gunakan caching untuk query berulang
- Limit search queries per request (max 3)
- Cek [official pricing](https://ai.google.dev/gemini-api/docs/pricing)

## 9. Next Steps

1. **Baca Dokumentasi Lengkap:** `docs/GOOGLE_GROUNDING_IMPLEMENTATION.md`
2. **Test Political Quotes:** Coba fitur pencarian quotes politisi
3. **Generate PDF:** Test dengan `enable_quote_images=True`
4. **Integrasi Email:** Test pengiriman email dengan hasil research

## 10. Support & Resources

- **Official Docs:** https://ai.google.dev/gemini-api/docs/grounding
- **Cookbook:** https://github.com/google-gemini/cookbook
- **Pricing:** https://ai.google.dev/gemini-api/docs/pricing
- **AI Studio:** https://makersuite.google.com/

---

**Ready to use!** 🚀

Agent sekarang menggunakan Google Grounding untuk real-time web search dengan citations otomatis.
