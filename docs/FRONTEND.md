# Gmail Chatbot UI - Frontend Documentation

Detailed documentation for the Gmail Chatbot Next.js frontend.

---

## Overview

The Gmail Chatbot UI is a **Next.js 16** application that provides:
- Modern chat interface for Gmail operations
- Real-time message display
- Integration with Gmail Agent backend API

---

## Technology Stack

| Technology | Version | Purpose |
|------------|---------|---------|
| Next.js | 16.1.2 | React framework with App Router |
| React | 19.2.3 | UI component library |
| TypeScript | 5.x | Type-safe JavaScript |
| Tailwind CSS | 4.x | Utility-first CSS framework |

---

## File Reference

### 📁 Project Structure

```
gmail-chatbot-ui/
├── src/
│   └── app/
│       ├── globals.css     # Global Tailwind styles
│       ├── layout.tsx      # Root layout (fonts, metadata)
│       └── page.tsx        # Main chat component
├── public/                 # Static assets
├── package.json            # Dependencies & scripts
├── next.config.ts          # Next.js configuration
├── tsconfig.json           # TypeScript config
├── postcss.config.mjs      # PostCSS (Tailwind) config
└── eslint.config.mjs       # ESLint rules
```

---

## Core Files Explained

### 1️⃣ `src/app/page.tsx` - Main Chat Component

**Role:** The primary chat interface component.

#### TypeScript Interface

```typescript
interface Message {
  id: string;           // Unique message identifier
  role: "user" | "assistant";  // Message sender
  content: string;      // Message text content
  action?: string;      // Action performed (send_email, fetch_emails, etc.)
  success?: boolean;    // Whether the action succeeded
}
```

#### Component State

```typescript
// Chat message history
const [messages, setMessages] = useState<Message[]>([
  {
    id: "welcome",
    role: "assistant",
    content: "Hello! I'm your email assistant...",
  },
]);

// Current input text
const [input, setInput] = useState("");

// Loading state for API calls
const [isLoading, setIsLoading] = useState(false);

// User ID for backend API
const userId = "pg-test-a199d8f3-e74a-42e0-956b-b1fbb2808b58";

// Ref for auto-scroll
const messagesEndRef = useRef<HTMLDivElement>(null);
```

#### Auto-Scroll Effect

```typescript
useEffect(() => {
  messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
}, [messages]);
```

#### Main Send Function

```typescript
const sendMessage = async () => {
  // 1. Validate - don't send empty or during loading
  if (!input.trim() || isLoading) return;

  // 2. Save input and add user message
  const currentInput = input;
  setMessages((prev) => [
    ...prev,
    { id: Date.now().toString(), role: "user", content: currentInput }
  ]);
  setInput("");
  setIsLoading(true);

  try {
    // 3. Call backend chat API
    const response = await fetch("http://localhost:8000/chat", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        message: currentInput,
        user_id: userId,
        auto_execute: true
      }),
    });

    const data = await response.json();
    
    // 4. Process response based on type
    let content = "";
    let action = "";
    let success = false;

    if (data.type === "action_result") {
      // Handle action results...
    } else if (data.type === "question") {
      content = data.message;
    }

    // 5. Add assistant response
    setMessages((prev) => [
      ...prev,
      { id: (Date.now() + 1).toString(), role: "assistant", content, action, success }
    ]);
    
  } catch (error) {
    // 6. Handle network errors
    setMessages((prev) => [
      ...prev,
      {
        id: (Date.now() + 1).toString(),
        role: "assistant",
        content: `❌ ${error instanceof Error ? error.message : "Connection failed"}`,
      }
    ]);
  } finally {
    setIsLoading(false);
  }
};
```

#### Response Formatting

```typescript
// Send Email Success
if (data.action === "send_email" && success) {
  content = `✅ Email sent!\n\n📧 ${data.intent.recipient_email}\n📝 ${data.intent.subject}\n\n${data.intent.body}`;
}

// Create Draft Success
else if (data.action === "create_draft" && success) {
  content = `✅ Draft created!\n\n📧 ${data.intent.recipient_email}\n📝 ${data.intent.subject}`;
}

// Fetch Emails Success
else if (data.action === "fetch_emails" && success) {
  const emails = data.result?.data?.data?.messages || [];
  if (emails.length > 0) {
    content = `📬 ${emails.length} emails:\n\n`;
    emails.forEach((email, i) => {
      content += `${i + 1}. ${email.subject}\n   ${email.sender}\n\n`;
    });
  } else {
    content = "📭 No emails.";
  }
}

// Error
else {
  content = `❌ Failed: ${data.result?.error || "Unknown error"}`;
}
```

#### UI Layout

```tsx
<div className="min-h-screen bg-gray-900 flex flex-col">
  {/* Header */}
  <header className="bg-gray-800 border-b border-gray-700 p-4">
    <h1>📧 Gmail Chatbot</h1>
    <span>🟢 Connected</span>
  </header>

  {/* Message List */}
  <main className="flex-1 overflow-y-auto p-4">
    {messages.map((msg) => (
      <MessageBubble key={msg.id} message={msg} />
    ))}
    {isLoading && <LoadingIndicator />}
  </main>

  {/* Input Footer */}
  <footer className="bg-gray-800 border-t border-gray-700 p-4">
    <input ... />
    <button onClick={sendMessage}>Send</button>
  </footer>
</div>
```

#### Message Bubble Styling

```tsx
// User message (right-aligned, blue)
<div className={`flex justify-end`}>
  <div className="max-w-[80%] rounded-2xl px-4 py-3 bg-blue-600 text-white">
    {msg.content}
  </div>
</div>

// Assistant message (left-aligned, dark gray)
<div className={`flex justify-start`}>
  <div className="max-w-[80%] rounded-2xl px-4 py-3 bg-gray-800 text-gray-100 border border-gray-700">
    {msg.content}
    {msg.action && (
      <div className={msg.success ? "text-green-400" : "text-red-400"}>
        {msg.action}
      </div>
    )}
  </div>
</div>
```

#### Loading Animation

```tsx
<div className="flex gap-1">
  <span className="w-2 h-2 bg-gray-500 rounded-full animate-bounce"></span>
  <span className="w-2 h-2 bg-gray-500 rounded-full animate-bounce" 
        style={{ animationDelay: "0.1s" }}></span>
  <span className="w-2 h-2 bg-gray-500 rounded-full animate-bounce" 
        style={{ animationDelay: "0.2s" }}></span>
</div>
```

---

### 2️⃣ `src/app/layout.tsx` - Root Layout

**Role:** Wraps all pages with common elements.

```typescript
import type { Metadata } from "next";
import { Geist, Geist_Mono } from "next/font/google";
import "./globals.css";

// Load Google Fonts
const geistSans = Geist({
  variable: "--font-geist-sans",
  subsets: ["latin"],
});

const geistMono = Geist_Mono({
  variable: "--font-geist-mono",
  subsets: ["latin"],
});

// Page metadata
export const metadata: Metadata = {
  title: "Create Next App",
  description: "Generated by create next app",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en">
      <body className={`${geistSans.variable} ${geistMono.variable} antialiased`}>
        {children}
      </body>
    </html>
  );
}
```

**Key Features:**
- Imports Geist font family (sans and mono variants)
- Sets CSS custom properties for font usage
- Applies antialiasing for smooth text rendering
- Provides page metadata (title, description)

---

### 3️⃣ `src/app/globals.css` - Global Styles

**Role:** Global CSS using Tailwind CSS v4.

```css
/* Import Tailwind CSS */
@import "tailwindcss";

/* CSS Variables for theming */
:root {
  --background: #ffffff;
  --foreground: #171717;
}

/* Tailwind theme inline configuration */
@theme inline {
  --color-background: var(--background);
  --color-foreground: var(--foreground);
  --font-sans: var(--font-geist-sans);
  --font-mono: var(--font-geist-mono);
}

/* Dark mode (system preference) */
@media (prefers-color-scheme: dark) {
  :root {
    --background: #0a0a0a;
    --foreground: #ededed;
  }
}

/* Base body styles */
body {
  background: var(--background);
  color: var(--foreground);
  font-family: Arial, Helvetica, sans-serif;
}
```

---

### 4️⃣ `package.json` - Project Configuration

```json
{
  "name": "gmail-chatbot-ui",
  "version": "0.1.0",
  "private": true,
  "scripts": {
    "dev": "next dev",
    "build": "next build",
    "start": "next start",
    "lint": "eslint"
  },
  "dependencies": {
    "next": "16.1.2",
    "react": "^19.2.3",
    "react-dom": "^19.2.3"
  },
  "devDependencies": {
    "@tailwindcss/postcss": "^4",
    "@types/node": "^20",
    "@types/react": "^19",
    "@types/react-dom": "^19",
    "eslint": "^9",
    "eslint-config-next": "16.1.2",
    "tailwindcss": "^4",
    "typescript": "^5"
  }
}
```

#### Available Scripts

| Script | Command | Description |
|--------|---------|-------------|
| `npm run dev` | `next dev` | Start dev server at http://localhost:3000 |
| `npm run build` | `next build` | Build production bundle |
| `npm run start` | `next start` | Start production server |
| `npm run lint` | `eslint` | Run ESLint checks |

---

## Component Flow Diagram

```
User Types Message
       │
       ▼
┌──────────────────┐
│  sendMessage()   │
│  - Validate      │
│  - Add to state  │
│  - Call API      │
└────────┬─────────┘
         │
         ▼
┌──────────────────┐     ┌─────────────────┐
│ Backend API      │────▶│ Groq LLM        │
│ POST /chat       │     │ Parse intent    │
└────────┬─────────┘     └─────────────────┘
         │
         ▼
┌──────────────────┐
│ Response Types:  │
│ - action_result  │
│ - question       │
│ - error          │
└────────┬─────────┘
         │
         ▼
┌──────────────────┐
│ Format Message   │
│ Add to messages  │
│ Update UI        │
└──────────────────┘
```

---

## Styling Guide

### Color Scheme (Dark Theme)

| Element | Color | Tailwind Class |
|---------|-------|----------------|
| Background | `#111827` | `bg-gray-900` |
| Header/Footer | `#1f2937` | `bg-gray-800` |
| User Message | `#2563eb` | `bg-blue-600` |
| Assistant Message | `#1f2937` | `bg-gray-800` |
| Border | `#374151` | `border-gray-700` |
| Text Primary | `#f3f4f6` | `text-gray-100` |
| Text Secondary | `#9ca3af` | `text-gray-400` |
| Success | `#4ade80` | `text-green-400` |
| Error | `#f87171` | `text-red-400` |

### UI Components

**Message Bubble:**
- Max width: 80%
- Border radius: 2xl (16px)
- Padding: px-4 py-3

**Input Field:**
- Background: gray-700
- Focus ring: blue-500
- Border radius: xl (12px)

**Send Button:**
- Background: blue-600
- Hover: blue-700
- Disabled: gray-600

---

## Running the Frontend

```bash
# Install dependencies
npm install

# Development mode
npm run dev
# → Opens at http://localhost:3000

# Production build
npm run build
npm run start
```

---

## Configuration

### Backend URL

The backend URL is currently hardcoded in `page.tsx`:

```typescript
const response = await fetch("http://localhost:8000/chat", {...});
```

For production, consider using environment variables:

```typescript
const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";
```

### User ID

The user ID is currently hardcoded:

```typescript
const userId = "pg-test-a199d8f3-e74a-42e0-956b-b1fbb2808b58";
```

In production, implement proper user authentication.

---

## Future Improvements

- [ ] Add user authentication
- [ ] Store conversation history
- [ ] Add connection status checking
- [ ] Support for OAuth flow in UI
- [ ] Mobile responsive improvements
- [ ] Dark/light theme toggle
