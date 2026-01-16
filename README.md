# Gmail Chatbot Project

This repository contains a full-stack application that acts as a Gmail Agent with a Chatbot UI. It uses **Composio** and **Groq** for the AI agent backend and **Next.js** for the frontend interface.

## Project Structure

- `gmail-agent/`: The backend API service built with Python and FastAPI.
- `gmail-chatbot-ui/`: The frontend user interface built with Next.js.

## Prerequisites

- **Python** (3.8+)
- **Node.js** (18+)
- **uv** (An extremely fast Python package installer and resolver) - [Installation Guide](https://github.com/astral-sh/uv)
- API Keys:
  - **Composio API Key**
  - **Groq API Key**

## Getting Started

Follow these steps to set up and run the project.

### 1. Backend Setup (`gmail-agent`)

Navigate to the agent directory:

```bash
cd gmail-agent
```

Create the `.env` file from the example:

```bash
cp .env.example .env
```

**Important:** Open the `.env` file and set your `COMPOSIO_API_KEY` and `GROQ_API_KEY`.

Create a virtual environment and install dependencies using `uv`:

```bash
uv venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate
uv pip install -r requirements.txt
```

Run the backend server:

```bash
uvicorn server.api:app --reload
```

The backend API will start at `http://localhost:8000`. You can view the API documentation at `http://localhost:8000/docs`.

### 2. Frontend Setup (`gmail-chatbot-ui`)

Open a new terminal and navigate to the UI directory:

```bash
cd gmail-chatbot-ui
```

Install dependencies:

```bash
npm install
# or yarn install / pnpm install / bun install
```

Run the development server:

```bash
npm run dev
# or yarn dev / pnpm dev / bun dev
```

The frontend will start at `http://localhost:3000`.

## Usage

1. Ensure the backend server is running on port `8000`.
2. Ensure the frontend server is running on port `3000`.
3. Open your browser and go to `http://localhost:3000`.
4. You can now chat with the Gmail Agent to send emails, fetch emails, or create drafts.

   **Example Commands:**
   - "Kirim email ke test@example.com tentang meeting besok"
   - "Ambil email terbaru"
   - "Buat draft email untuk john@doe.com"

## API Endpoints (Backend)

- `POST /connection/exists`: Check connection status.
- `POST /connection/create`: Create a new connection.
- `POST /connection/status`: Get connection status.
- `POST /actions/send_email`: Send an email.
- `POST /actions/fetch_emails`: Fetch emails.
- `POST /actions/create_draft`: Create an email draft.
- `POST /chat`: Chat endpoint used by the frontend.
