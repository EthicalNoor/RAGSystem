# RAG Control Center

A production-grade Retrieval-Augmented Generation (RAG) dashboard and API. This system allows you to upload documents, process them into vector embeddings using PostgreSQL (`pgvector`), and interact with them using an intelligent chat interface powered by dynamic LLM providers (Google Gemini / OpenAI).

## Prerequisites

Before you begin, ensure you have the following installed on your machine:
* **Python 3.10+**
* **Node.js 18+** and **npm** (or yarn/pnpm)
* **PostgreSQL 15+** with the **`pgvector`** extension installed and running.

---

## Part 1: Backend Setup (FastAPI)

The backend handles document parsing, vector database management, and LLM communication.

### 1. Environment Configuration
Navigate to your `backend` directory and create a `.env` file with the following configuration. Ensure you add at least one valid AI provider API key.

```env
# backend/.env
HOST=0.0.0.0
PORT=8000
ENVIRONMENT=development
CORS_ORIGINS=http://localhost:5173

# Database (Update with your PostgreSQL credentials)
DATABASE_URL=postgresql://postgres:root@localhost:5432/RagDB

# AI Provider Credentials
OPENAI_API_KEY=your_openai_api_key_here
GEMINI_API_KEY=your_gemini_api_key_here

# Default Settings
API_PROVIDER=gemini
EMBEDDING_MODEL=models/text-embedding-004
LLM_MODEL=gemini-1.5-pro
CHUNK_SIZE=1024
TEMPERATURE=0.2
UPLOAD_DIR=./uploads
```

### 2. Install and Run
Open a terminal, navigate to the `backend` directory, and run the following commands:

```bash
# 1. Create and activate a virtual environment
python -m venv venv

# On Windows:
venv\Scripts\activate
# On macOS/Linux:
source venv/bin/activate

# 2. Install dependencies
pip install -r requirements.txt

# 3. Start the server (Database tables will auto-initialize on first run)
python main.py
```
*The API is now running at `http://localhost:8000`. You can view the interactive Swagger documentation at `http://localhost:8000/docs`.*

---

## Part 2: Frontend Setup (React + Vite)

The frontend is a modern React Single Page Application (SPA) that acts as the control center for your RAG system.

### 1. Environment Configuration
Navigate to your `frontend` directory and create a `.env` file. 

```env
# frontend/.env
VITE_API_BASE_URL=http://localhost:8000/api/v1
VITE_APP_TITLE="RAG Control Center"
```

### 2. Install and Run
Open a new terminal window, navigate to the `frontend` directory, and start the development server:

```bash
# 1. Install dependencies
npm install

# 2. Start the Vite development server
npm run dev
```
*The frontend is now running at `http://localhost:5173`. Open this URL in your browser.*

---

## Getting Started

Once both the backend and frontend servers are running:

1. **Verify Settings:** Navigate to the **Settings** tab in the UI to ensure your API keys and models are configured correctly.
2. **Upload Knowledge:** Go to the **Documents** tab and drag-and-drop your PDFs. The backend will parse and index them in the background.
3. **Ask AI:** Once your documents display an "Indexed" status, go to the **Ask AI** tab to start querying your secure knowledge base.