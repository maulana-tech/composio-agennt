# Quote Image Generator Tools

This document describes the quote image generation tools available in the Gmail Agent system.

## Overview

The system provides 4 different quote image generators, each optimized for specific use cases:

| Tool | Technology | Best For |
|------|------------|----------|
| `generate_quote_image_tool` | Pillow | Accurate text, solid background |
| `generate_and_send_quote_email` | Pillow + Composio | Generate + send via email |
| `generate_dalle_quote_image_tool` | OpenAI DALL-E 3 | Artistic AI-generated images |
| `generate_quote_with_person_photo` | Pillow + Serper | Person's photo as background |

---

## 1. Pillow Quote Generator

**File:** `server/tools/pillow_quote_generator.py`

### Features
- ✅ 100% accurate text rendering (no AI typos)
- ✅ Fast generation (~1 second)
- ✅ Professional minimalist design
- ✅ Landscape format (1792x1024)

### Usage
```python
from server.tools.pillow_quote_generator import generate_quote_image_tool

result = generate_quote_image_tool.invoke({
    "quote_text": "We are committed to building a strong defense.",
    "author": "Prabowo Subianto",
    "context": "Presidential Address, 2025"
})
```

### Output
- **Location:** `attachment/quote_{author}_{timestamp}.png`
- **Size:** ~50-60 KB

---

## 2. DALL-E Quote Generator

**File:** `server/tools/dalle_quote_generator.py`

### Features
- 🎨 AI-generated artistic visuals
- 🖼️ Supports multiple styles (digital art, watercolor, photorealistic)
- ⚠️ Text may have minor imperfections (AI limitation)
- 🕐 Slower generation (~15-30 seconds)

### Requirements
- `OPENAI_API_KEY` environment variable

### Usage
```python
from server.tools.dalle_quote_generator import generate_dalle_quote_image_tool

result = generate_dalle_quote_image_tool.invoke({
    "quote_text": "The future belongs to those who believe.",
    "author": "Eleanor Roosevelt",
    "context": "Speech, 1940",
    "style": "watercolor"
})
```

### Output
- **Location:** `attachment/dalle_quote_{author}_{timestamp}.png`
- **Size:** ~200-500 KB

---

## 3. Avatar Quote Generator (Person Photo Background)

**File:** `server/tools/avatar_quote_generator.py`

### Features
- 🔍 Auto-searches for person's photo from Google
- 👤 Works with any person (politicians, historical figures, celebrities)
- 🖼️ Photo used as blurred background with dark overlay
- ✅ 100% accurate text rendering
- 🎯 Professional design with shadow effects

### Requirements
- `SERPER_API_KEY` environment variable (for Google Image Search)

### Usage
```python
from server.tools.avatar_quote_generator import generate_quote_with_person_photo

result = generate_quote_with_person_photo.invoke({
    "quote_text": "We shall fight on the beaches.",
    "person_name": "Winston Churchill",
    "context": "House of Commons, 1940"
})
```

### Supported Persons
- Politicians: Prabowo Subianto, Joko Widodo, Joe Biden, etc.
- Historical Figures: Adolf Hitler, Joseph Stalin, Winston Churchill, etc.
- Celebrities: Elon Musk, Mark Zuckerberg, etc.
- Anyone with photos available online

### Output
- **Location:** `attachment/avatar_quote_{person}_{timestamp}.png`
- **Size:** ~500-800 KB (larger due to photo background)

---

## 4. Quote + Email Sender

**File:** `server/tools/pillow_quote_generator.py`

### Features
- 📧 Combines quote generation with email sending
- 📎 Automatically attaches the generated image
- ✉️ Professional email formatting

### Requirements
- `COMPOSIO_API_KEY` environment variable
- Gmail account connected in Composio

### Usage
```python
from server.tools.pillow_quote_generator import generate_and_send_quote_email

result = generate_and_send_quote_email.invoke({
    "quote_text": "The only thing we have to fear is fear itself.",
    "author": "Franklin D. Roosevelt",
    "recipient_email": "user@example.com",
    "context": "Inaugural Address, 1933",
    "subject": "Inspirational Quote",
    "additional_message": "Hope you enjoy this quote!"
})
```

---

## Agent Prompt Examples

The AI agent automatically selects the appropriate tool based on user prompts:

```
"Buatkan gambar quote tentang pertahanan"
→ generate_quote_image_tool (Pillow basic)

"Buatkan gambar quote Prabowo dengan fotonya"
→ generate_quote_with_person_photo (Avatar)

"Buatkan quote artistic style watercolor"
→ generate_dalle_quote_image_tool (DALL-E)

"Generate quote dan kirim ke email saya"
→ generate_and_send_quote_email

"Create a quote image of Hitler with his photo in the background"
→ generate_quote_with_person_photo (Avatar)
```

---

## Environment Variables

Required environment variables in `.env`:

```bash
# For DALL-E quote generator
OPENAI_API_KEY=sk-...

# For Avatar quote generator (image search)
SERPER_API_KEY=...

# For email sending
COMPOSIO_API_KEY=...
```

---

## Output Directory

All generated images are saved to:
```
/gmail-agent/attachment/
```

File naming convention:
- Pillow: `quote_{author}_{timestamp}.png`
- DALL-E: `dalle_quote_{author}_{timestamp}.png`
- Avatar: `avatar_quote_{person}_{timestamp}.png`
