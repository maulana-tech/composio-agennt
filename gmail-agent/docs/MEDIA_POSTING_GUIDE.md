# Social Media Posting with Images/Videos

## Overview

Composio SDK provides **automatic file handling** for media uploads. You can simply pass local file paths or URLs directly to social media posting tools without manual upload steps.

---

## Twitter Media Posting

### Tool: `TWITTER_CREATE_TWEET_WITH_MEDIA`

**Parameters:**
- `text`: Tweet content (string)
- `media`: File path (local) or URL (string)

### Examples

#### 1. Using Local File Path
```python
import os
from composio import Composio

composio = Composio(api_key=os.environ.get("COMPOSIO_API_KEY"))

# Post tweet with local image
result = composio.tools.execute(
    "TWITTER_CREATE_TWEET_WITH_MEDIA",
    user_id="default",
    arguments={
        "text": "Check out this awesome quote! 🎨",
        "media": "/Users/em/web/AI-Agent/composio-agent/gmail-agent/quotes/leadership_quote.png"
    }
)

print(result)
```

#### 2. Using Image URL
```python
result = composio.tools.execute(
    "TWITTER_CREATE_TWEET_WITH_MEDIA",
    user_id="default",
    arguments={
        "text": "Tweet with image from URL!",
        "media": "https://example.com/image.jpg"
    }
)
```

#### 3. Agent Integration
```python
# Agent automatically handles this:
# 1. User: "Create a leadership quote and post to Twitter"
# 2. Agent calls generate_quote_image → gets file path
# 3. Agent calls TWITTER_CREATE_TWEET_WITH_MEDIA with file path
# 4. Composio uploads file automatically → Tweet posted!

from composio import Composio
from langchain_groq import ChatGroq
from langchain.agents import create_tool_calling_agent, AgentExecutor

composio = Composio(api_key=os.environ.get("COMPOSIO_API_KEY"))
session = composio.create(user_id="default", toolkits=["twitter"])
tools = session.tools()

# Add quote generation tool
from server.tools.quote_generator import generate_quote_image_tool
all_tools = [generate_quote_image_tool] + tools

llm = ChatGroq(model="llama-3.3-70b-versatile")
agent = create_tool_calling_agent(llm, all_tools, prompt)
executor = AgentExecutor(agent=agent, tools=all_tools)

result = executor.invoke({
    "input": "Create a quote about leadership and post to Twitter"
})
```

---

## Facebook Media Posting

### Tool: `FACEBOOK_CREATE_PHOTO_POST`

**Parameters:**
- `page_id`: Facebook Page ID (string, required)
- `message`: Post caption/text (string)
- `url`: Image URL (string) OR `photo`: Local file path (string)

### Examples

#### 1. Using Local File
```python
result = composio.tools.execute(
    "FACEBOOK_CREATE_PHOTO_POST",
    user_id="default",
    arguments={
        "page_id": "123456789",  # Your Facebook Page ID
        "message": "Leadership wisdom for today! 💡",
        "photo": "/path/to/quote_image.png"
    }
)
```

#### 2. Using URL
```python
result = composio.tools.execute(
    "FACEBOOK_CREATE_PHOTO_POST",
    user_id="default",
    arguments={
        "page_id": "123456789",
        "message": "Check this out!",
        "url": "https://example.com/image.jpg"
    }
)
```

### Finding Your Facebook Page ID

#### Method 1: Via Facebook Page Settings
1. Go to your Facebook Page
2. Click "About" tab
3. Scroll down to "Page ID" or "Page Transparency"
4. Copy the numeric ID

#### Method 2: Via URL
1. Go to your page: `facebook.com/yourpage`
2. Page ID is in the URL or page info

#### Method 3: Via Composio API
```python
# Coming soon: Tool to list connected Facebook Pages
result = composio.tools.execute(
    "FACEBOOK_LIST_PAGES",
    user_id="default",
    arguments={}
)
# Returns list of pages with IDs
```

---

## Instagram Media Posting

### Requirements
- ✅ Instagram Business or Creator account
- ✅ Connected to a Facebook Page
- ✅ Account authorized via Composio

### Tool: `INSTAGRAM_CREATE_PHOTO_POST`

**Parameters:**
- `caption`: Post caption (string)
- `image_url`: Image URL (string) OR `image`: Local file path (string)

### Example
```python
result = composio.tools.execute(
    "INSTAGRAM_CREATE_PHOTO_POST",
    user_id="default",
    arguments={
        "caption": "Daily inspiration 🌟 #Leadership #Quotes",
        "image": "/path/to/quote_image.png"
    }
)
```

---

## File Format Support

### Images
- ✅ JPG/JPEG
- ✅ PNG
- ✅ GIF (Twitter/Facebook)
- ✅ WEBP

### Videos
- ✅ MP4
- ✅ MOV
- ⚠️ Max file sizes vary by platform:
  - Twitter: 512MB video, 5MB image
  - Facebook: 4GB video, 10MB image
  - Instagram: 100MB video, 8MB image

---

## Automatic File Handling

Composio SDK handles:
1. ✅ **File Reading** - Reads local files automatically
2. ✅ **Upload** - Uploads to platform's media endpoint
3. ✅ **Media ID** - Gets media ID from platform
4. ✅ **Post Creation** - Attaches media to post
5. ✅ **Error Handling** - Validates file size, format, etc.

**You just need to:**
- Provide file path or URL
- Composio does the rest!

---

## Complete Example: Quote to Social Media

### End-to-End Flow

```python
from composio import Composio
from langchain_groq import ChatGroq
from langchain.agents import create_tool_calling_agent, AgentExecutor
from server.tools.quote_generator import generate_quote_image_tool

# Setup
composio = Composio(api_key=os.environ.get("COMPOSIO_API_KEY"))
session = composio.create(
    user_id="default",
    toolkits=["twitter", "facebook", "instagram"]
)

tools = session.tools()
all_tools = [generate_quote_image_tool] + tools

llm = ChatGroq(
    model="llama-3.3-70b-versatile",
    api_key=os.environ.get("GROQ_API_KEY")
)

agent = create_tool_calling_agent(llm, all_tools, prompt)
executor = AgentExecutor(agent=agent, tools=all_tools, verbose=True)

# Execute
result = executor.invoke({
    "input": """
    Create a quote about leadership with a modern design.
    Post it to Twitter, Facebook (page ID: 123456789), and Instagram.
    Use the caption: "Leadership wisdom for today! 💡 #Leadership #Quotes"
    """
})

print(result)
```

### Agent Will:
1. Call `generate_quote_image` → Get `/path/to/quote.png`
2. Call `TWITTER_CREATE_TWEET_WITH_MEDIA`:
   ```json
   {
     "text": "Leadership wisdom for today! 💡 #Leadership #Quotes",
     "media": "/path/to/quote.png"
   }
   ```
3. Call `FACEBOOK_CREATE_PHOTO_POST`:
   ```json
   {
     "page_id": "123456789",
     "message": "Leadership wisdom for today! 💡 #Leadership #Quotes",
     "photo": "/path/to/quote.png"
   }
   ```
4. Call `INSTAGRAM_CREATE_PHOTO_POST`:
   ```json
   {
     "caption": "Leadership wisdom for today! 💡 #Leadership #Quotes",
     "image": "/path/to/quote.png"
   }
   ```

All uploads handled automatically by Composio! ✨

---

## Troubleshooting

### File Not Found Error
```python
# ❌ Relative path might fail
"media": "quote.png"

# ✅ Use absolute path
import os
"media": os.path.abspath("quote.png")

# ✅ Or from quote generator output
quote_result = generate_quote_image({"topic": "leadership"})
"media": quote_result["image_path"]  # Already absolute
```

### Image Too Large
- Resize before uploading
- Use image optimization tools
- Or use URL to hosted image (CDN)

### Invalid Format
- Convert to supported formats (JPG, PNG)
- Check file isn't corrupted

### Upload Fails
- Verify file exists: `os.path.exists(file_path)`
- Check file permissions
- Ensure connection is ACTIVE

---

## Testing Media Upload

### Quick Test Script
```python
import os
from composio import Composio

composio = Composio(api_key=os.environ.get("COMPOSIO_API_KEY"))

# Test with a sample image
test_image = "/path/to/test.jpg"

if not os.path.exists(test_image):
    print(f"❌ Test image not found: {test_image}")
else:
    print(f"✅ Test image found: {test_image}")
    
    result = composio.tools.execute(
        "TWITTER_CREATE_TWEET_WITH_MEDIA",
        user_id="default",
        arguments={
            "text": "Test tweet with image! 🎨",
            "media": test_image
        }
    )
    
    if result.get("successful"):
        print("✅ Media upload successful!")
        print(f"Tweet URL: {result.get('data', {}).get('url', 'N/A')}")
    else:
        print(f"❌ Upload failed: {result.get('error')}")
```

---

## Best Practices

1. **Use Absolute Paths**
   ```python
   import os
   image_path = os.path.abspath("quote.png")
   ```

2. **Validate Files Before Upload**
   ```python
   if not os.path.exists(image_path):
       raise FileNotFoundError(f"Image not found: {image_path}")
   ```

3. **Handle Errors Gracefully**
   ```python
   try:
       result = composio.tools.execute(...)
   except Exception as e:
       print(f"Upload failed: {e}")
   ```

4. **Clean Up After Upload (Optional)**
   ```python
   # After successful post
   if os.path.exists(temp_image):
       os.remove(temp_image)
   ```

---

## Additional Resources

- [Composio Automatic File Handling Docs](https://docs.composio.dev/docs/tools-direct/executing-tools)
- [Twitter Toolkit Docs](https://docs.composio.dev/toolkits/twitter)
- [Facebook Toolkit Docs](https://docs.composio.dev/toolkits/facebook)
- [Request New Tools](https://requests.composio.dev)
