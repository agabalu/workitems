#!/usr/bin/env python3
"""
Wiki Knowledge Base Question-Answering API
Uses extracted wiki content to answer user questions via LLM
"""

from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from typing import List, Dict, Optional
import json
import os
import requests
import asyncio
from datetime import datetime
import re
import sys
import logging

# Add the parent directory to the path to import config
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Import environment-based configuration
try:
    from config.settings import (
        get_default_host, get_default_port, get_env_int,
        security_config, logger, get_port, get_host
    )
    CONFIG_AVAILABLE = True
    logger.info("✅ Environment-based configuration loaded for Wiki Q&A API")
except ImportError as e:
    CONFIG_AVAILABLE = False
    print(f"⚠️ Could not load environment configuration: {e}")
    print("   Using fallback configuration")

    # Fallback logging setup
    logging.basicConfig(level=logging.INFO)
    logger = logging.getLogger(__name__)

# Environment-based configuration
def get_api_config():
    """Get API configuration from environment variables"""
    if CONFIG_AVAILABLE:
        # Use environment-based configuration
        host = os.getenv('WIKI_QA_API_HOST', get_default_host())
        port = get_env_int('WIKI_QA_API_PORT', 8002)

        # Azure OpenAI configuration from environment
        azure_config = {
            'api_base': os.getenv('AZURE_OPENAI_BASE_URL', '<< Base URL here >>'),
            'api_key': os.getenv('AZURE_OPENAI_API_KEY', '<< API Key Here >>>'),
            'deployment_name': os.getenv('AZURE_OPENAI_DEPLOYMENT', '<< deployment name >>'),
            'api_version': os.getenv('AZURE_OPENAI_API_VERSION', '2024-05-01-preview')
        }
    else:
        # Fallback configuration
        host = os.getenv('DEFAULT_HOST', 'localhost')
        port = int(os.getenv('WIKI_QA_API_PORT', '8002'))

        azure_config = {
            'api_base': '<< your api base here >>',
            'api_key': '<< your api key here >>',
            'deployment_name': '<< your deployment name here >>',
            'api_version': '2024-05-01-preview'
        }

    return {
        'host': host,
        'port': port,
        'azure': azure_config,
        'wiki_extraction_dir': os.getenv('WIKI_EXTRACTION_DIR', os.path.dirname(os.path.abspath(__file__))),
        'max_tokens_default': get_env_int('WIKI_QA_MAX_TOKENS', 1000) if CONFIG_AVAILABLE else int(os.getenv('WIKI_QA_MAX_TOKENS', '1000')),
        'timeout': get_env_int('WIKI_QA_TIMEOUT', 30) if CONFIG_AVAILABLE else int(os.getenv('WIKI_QA_TIMEOUT', '30'))
    }

# Get configuration
api_config = get_api_config()

# Initialize FastAPI app with environment-based configuration
app = FastAPI(
    title="Wiki Knowledge Base Q&A API",
    description="Ask questions about Intel Platform CI processes using wiki knowledge base",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc"
)

class QuestionRequest(BaseModel):
    question: str
    max_tokens: Optional[int] = api_config['max_tokens_default']
    include_sources: Optional[bool] = True

class AnswerResponse(BaseModel):
    question: str
    answer: str
    sources: List[Dict]
    confidence_score: Optional[float]
    response_time: float
    timestamp: str

class WikiKnowledgeBase:
    def __init__(self, wiki_extraction_file: str):
        """Initialize the knowledge base from extracted wiki content"""
        self.wiki_data = None
        self.pages = {}
        self.load_wiki_data(wiki_extraction_file)

        # Azure OpenAI configuration from environment
        azure_config = api_config['azure']
        self.api_base = azure_config['api_base']
        self.api_key = azure_config['api_key']
        self.deployment_name = azure_config['deployment_name']
        self.api_version = azure_config['api_version']

        # Build the full endpoint URL
        self.endpoint_url = f"{self.api_base}openai/deployments/{self.deployment_name}/chat/completions?api-version={self.api_version}"

        logger.info(f"🔧 Azure OpenAI configured: {self.deployment_name} at {self.api_base}")

    def load_wiki_data(self, extraction_file: str):
        """Load extracted wiki data from JSON file"""
        try:
            with open(extraction_file, 'r', encoding='utf-8') as f:
                self.wiki_data = json.load(f)

            # Build searchable pages dictionary
            for page_id, page_data in self.wiki_data.get('pages', {}).items():
                if page_data.get('success', False):
                    self.pages[page_id] = {
                        'title': page_data['page_info']['title'],
                        'content': page_data['content'],
                        'url': page_data['page_info']['web_url'],
                        'version': page_data['page_info']['version'],
                        'content_length': page_data['content_length']
                    }

            logger.info(f"✅ Loaded {len(self.pages)} wiki pages into knowledge base")
            for page_id, page in self.pages.items():
                logger.info(f"  - {page_id}: {page['title']} ({page['content_length']} chars)")

        except Exception as e:
            logger.error(f"❌ Error loading wiki data: {e}")
            self.wiki_data = {"pages": {}}
            self.pages = {}

    def search_relevant_content(self, question: str, max_pages: int = 3) -> List[Dict]:
        """Search for relevant wiki pages based on the question"""
        question_lower = question.lower()

        # Simple keyword-based relevance scoring
        relevant_pages = []

        for page_id, page in self.pages.items():
            title_lower = page['title'].lower()
            content_lower = page['content'].lower()

            # Calculate relevance score
            score = 0

            # Title matches are highly relevant
            for word in question_lower.split():
                if word in title_lower:
                    score += 10
                if word in content_lower:
                    score += 1

            # Boost score for specific topics
            if any(keyword in question_lower for keyword in ['precheck', 'prechecks']):
                if any(term in title_lower for term in ['precheck', 'prechecks']):
                    score += 20

            if any(keyword in question_lower for keyword in ['platform', 'ci', 'build']):
                if any(term in title_lower for term in ['platform', 'ci', 'build']):
                    score += 15

            if score > 0:
                relevant_pages.append({
                    'page_id': page_id,
                    'title': page['title'],
                    'content': page['content'],
                    'url': page['url'],
                    'relevance_score': score
                })

        # Sort by relevance and return top results
        relevant_pages.sort(key=lambda x: x['relevance_score'], reverse=True)
        return relevant_pages[:max_pages]

    def create_context_prompt(self, question: str, relevant_pages: List[Dict]) -> str:
        """Create a context-rich prompt for the LLM"""

        context_sections = []
        for page in relevant_pages:
            context_sections.append(f"""
**Source: {page['title']}**
**URL: {page['url']}**
**Content:**
{page['content'][:2000]}...
""")

        context = "\n".join(context_sections)

        prompt = f"""You are a knowledgeable assistant helping users understand Intel Platform CI processes. Use the following wiki documentation to answer the user's question comprehensively and accurately.

**CONTEXT FROM INTEL WIKI PAGES:**
{context}

**USER QUESTION:**
{question}

**INSTRUCTIONS:**
1. Answer the question using ONLY the information provided in the context above
2. Be specific and detailed in your response
3. If the context doesn't contain enough information to fully answer the question, state what information is available and what is missing
4. Reference the relevant wiki page titles when citing information
5. Use clear, professional language appropriate for technical documentation

**ANSWER:**"""

        return prompt

    async def get_llm_response(self, prompt: str, max_tokens: int = None) -> str:
        """Get response from Azure OpenAI LLM using direct HTTP requests"""
        if max_tokens is None:
            max_tokens = api_config['max_tokens_default']

        try:
            # Prepare the request payload
            payload = {
                "messages": [
                    {
                        "role": "system",
                        "content": "You are an expert assistant for Intel Platform CI processes. Provide accurate, detailed answers based on the provided wiki documentation."
                    },
                    {
                        "role": "user",
                        "content": prompt
                    }
                ],
                "max_tokens": max_tokens,
                "temperature": 0.3,
                "top_p": 0.9
            }

            # Prepare headers
            headers = {
                "Content-Type": "application/json",
                "api-key": self.api_key
            }

            # Make the HTTP request with environment-based timeout
            response = requests.post(
                self.endpoint_url,
                headers=headers,
                json=payload,
                timeout=api_config['timeout']
            )

            # Check if request was successful
            response.raise_for_status()

            # Parse the response
            response_data = response.json()

            # Extract the generated text
            if 'choices' in response_data and len(response_data['choices']) > 0:
                return response_data['choices'][0]['message']['content'].strip()
            else:
                return "Sorry, I couldn't generate a response. Please try again."

        except requests.exceptions.RequestException as e:
            logger.error(f"HTTP request error: {e}")
            raise Exception(f"HTTP request error: {str(e)}")
        except Exception as e:
            logger.error(f"LLM API error: {e}")
            raise Exception(f"LLM API error: {str(e)}")

    async def answer_question(self, question: str, max_tokens: int = None, include_sources: bool = True) -> Dict:
        """Main method to answer a question using the wiki knowledge base"""
        if max_tokens is None:
            max_tokens = api_config['max_tokens_default']

        start_time = datetime.now()

        try:
            # Find relevant wiki content
            relevant_pages = self.search_relevant_content(question)

            if not relevant_pages:
                return {
                    "answer": "I couldn't find relevant information in the wiki knowledge base to answer your question. Please try rephrasing your question or asking about Platform CI processes, prechecks, or build workflows.",
                    "sources": [],
                    "confidence_score": 0.0,
                    "response_time": (datetime.now() - start_time).total_seconds()
                }

            # Create context prompt
            prompt = self.create_context_prompt(question, relevant_pages)

            # Get LLM response
            answer = await self.get_llm_response(prompt, max_tokens)

            # Prepare response
            sources = []
            if include_sources:
                sources = [
                    {
                        "title": page['title'],
                        "url": page['url'],
                        "relevance_score": page['relevance_score']
                    }
                    for page in relevant_pages
                ]

            response_time = (datetime.now() - start_time).total_seconds()

            return {
                "answer": answer,
                "sources": sources,
                "confidence_score": min(relevant_pages[0]['relevance_score'] / 50.0, 1.0) if relevant_pages else 0.0,
                "response_time": response_time
            }

        except Exception as e:
            raise Exception(f"Error processing question: {str(e)}")

# Initialize knowledge base (will be loaded when the API starts)
knowledge_base = None

@app.on_event("startup")
async def startup_event():
    """Initialize the knowledge base on startup"""
    global knowledge_base

    # Look for the most recent wiki extraction file
    extraction_dir = api_config['wiki_extraction_dir']

    # Also check the config directory for extraction files
    config_dir = os.path.join(os.path.dirname(extraction_dir), 'config')
    search_dirs = [extraction_dir, config_dir]

    extraction_files = []
    for search_dir in search_dirs:
        if os.path.exists(search_dir):
            files = [f for f in os.listdir(search_dir) if f.startswith('wiki_extraction') and f.endswith('.json')]
            extraction_files.extend([os.path.join(search_dir, f) for f in files])

    if not extraction_files:
        logger.error("❌ No wiki extraction files found. Please run wiki_extractor.py first.")
        return

    # Use the most recent extraction file
    latest_file = sorted(extraction_files, key=os.path.getmtime)[-1]

    logger.info(f"🚀 Initializing knowledge base with: {os.path.basename(latest_file)}")
    knowledge_base = WikiKnowledgeBase(latest_file)

@app.get("/")
async def root():
    """Root endpoint with API information"""
    return {
        "message": "Wiki Knowledge Base Q&A API",
        "version": "1.0.0",
        "configuration": {
            "host": api_config['host'],
            "port": api_config['port'],
            "environment_config_loaded": CONFIG_AVAILABLE,
            "azure_openai_deployment": api_config['azure']['deployment_name']
        },
        "endpoints": {
            "ask": "/ask - Ask a question about Platform CI processes",
            "health": "/health - Check API health",
            "knowledge_base_info": "/kb-info - Get knowledge base statistics",
            "config": "/config - Get current configuration"
        },
        "example_questions": [
            "What is Platform CI?",
            "How do prechecks work?",
            "What is the difference between bronze, silver, and gold builds?",
            "What are BKC configurations?",
            "How do I run prechecks from ABI?"
        ]
    }

@app.get("/config")
async def get_config():
    """Get current API configuration"""
    return {
        "api_configuration": {
            "host": api_config['host'],
            "port": api_config['port'],
            "max_tokens_default": api_config['max_tokens_default'],
            "timeout": api_config['timeout'],
            "environment_config_available": CONFIG_AVAILABLE
        },
        "azure_openai": {
            "deployment_name": api_config['azure']['deployment_name'],
            "api_version": api_config['azure']['api_version'],
            "base_url": api_config['azure']['api_base']
        },
        "knowledge_base": {
            "extraction_directory": api_config['wiki_extraction_dir'],
            "pages_loaded": len(knowledge_base.pages) if knowledge_base else 0
        }
    }

@app.post("/ask", response_model=AnswerResponse)
async def ask_question(request: QuestionRequest):
    """Ask a question about Platform CI processes"""
    if not knowledge_base:
        raise HTTPException(status_code=503, detail="Knowledge base not initialized. Please check server startup logs.")

    if not request.question or len(request.question.strip()) < 3:
        raise HTTPException(status_code=400, detail="Question must be at least 3 characters long.")

    try:
        result = await knowledge_base.answer_question(
            question=request.question,
            max_tokens=request.max_tokens,
            include_sources=request.include_sources
        )

        return AnswerResponse(
            question=request.question,
            answer=result["answer"],
            sources=result["sources"],
            confidence_score=result["confidence_score"],
            response_time=result["response_time"],
            timestamp=datetime.now().isoformat()
        )

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error processing question: {str(e)}")

@app.get("/ask")
async def ask_question_get(
    q: str = Query(..., description="Your question about Platform CI processes", min_length=3),
    max_tokens: int = Query(api_config['max_tokens_default'], description="Maximum tokens for the response"),
    include_sources: bool = Query(True, description="Include source wiki pages in response")
):
    """Ask a question via GET request (for simple testing)"""
    request = QuestionRequest(
        question=q,
        max_tokens=max_tokens,
        include_sources=include_sources
    )
    return await ask_question(request)

@app.get("/health")
async def health_check():
    """Health check endpoint"""
    if not knowledge_base:
        return JSONResponse(
            status_code=503,
            content={
                "status": "unhealthy",
                "message": "Knowledge base not initialized",
                "timestamp": datetime.now().isoformat(),
                "configuration": {
                    "host": api_config['host'],
                    "port": api_config['port'],
                    "environment_config_loaded": CONFIG_AVAILABLE
                }
            }
        )

    return {
        "status": "healthy",
        "knowledge_base_loaded": len(knowledge_base.pages) > 0,
        "total_pages": len(knowledge_base.pages),
        "configuration": {
            "host": api_config['host'],
            "port": api_config['port'],
            "environment_config_loaded": CONFIG_AVAILABLE
        },
        "timestamp": datetime.now().isoformat()
    }

@app.get("/kb-info")
async def knowledge_base_info():
    """Get information about the loaded knowledge base"""
    if not knowledge_base:
        raise HTTPException(status_code=503, detail="Knowledge base not initialized")

    pages_info = []
    for page_id, page in knowledge_base.pages.items():
        pages_info.append({
            "page_id": page_id,
            "title": page["title"],
            "content_length": page["content_length"],
            "url": page["url"]
        })

    return {
        "total_pages": len(knowledge_base.pages),
        "extraction_timestamp": knowledge_base.wiki_data.get("extracted_at"),
        "successful_extractions": knowledge_base.wiki_data.get("successful_extractions", 0),
        "pages": pages_info,
        "configuration": {
            "host": api_config['host'],
            "port": api_config['port']
        }
    }

if __name__ == "__main__":
    import uvicorn

    # Use environment-based configuration
    host = api_config['host']
    port = api_config['port']

    logger.info(f"🚀 Starting Wiki Q&A API on {host}:{port}")
    logger.info(f"📚 API docs available at http://{host}:{port}/docs")
    logger.info(f"🔧 Environment config loaded: {CONFIG_AVAILABLE}")

    uvicorn.run(app, host=host, port=port)
