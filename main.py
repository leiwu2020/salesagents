import os
import sqlite3
import json
from datetime import datetime, timedelta
from typing import List, Optional
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from openai import OpenAI
from dotenv import load_dotenv

load_dotenv()

app = FastAPI()
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

# Database helper
def query_db(query, args=(), one=False):
    conn = sqlite3.connect('sales.db')
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()
    cur.execute(query, args)
    rv = cur.fetchall()
    conn.close()
    return (rv[0] if rv else None) if one else rv

# Tools for the AI agent
def get_customers():
    """Get all customers in the database."""
    rows = query_db('SELECT * FROM customers')
    return [dict(row) for row in rows]

def search_customers(query: str):
    """Search for customers by name, company, or notes."""
    rows = query_db("SELECT * FROM customers WHERE name LIKE ? OR company LIKE ? OR notes LIKE ?", 
                   (f'%{query}%', f'%{query}%', f'%{query}%'))
    return [dict(row) for row in rows]

def get_urgent_follow_ups():
    """Get customers who need a follow-up soon (within 2 days)."""
    now = datetime.now().isoformat()
    two_days_later = (datetime.now() + timedelta(days=2)).isoformat()
    rows = query_db("SELECT * FROM customers WHERE next_follow_up IS NOT NULL AND next_follow_up <= ?", 
                   (two_days_later,))
    return [dict(row) for row in rows]

def get_customer_details(customer_id: int):
    """Get detailed information about a specific customer by ID."""
    row = query_db("SELECT * FROM customers WHERE id = ?", (customer_id,), one=True)
    return dict(row) if row else None

def add_to_knowledge_base(entity_name: str, relation: str, target_entity: str, additional_info: str = ""):
    """Add a new fact or piece of information to the knowledge base."""
    conn = sqlite3.connect('sales.db')
    cursor = conn.cursor()
    cursor.execute('''
        INSERT INTO knowledge_base (entity_name, relation, target_entity, additional_info)
        VALUES (?, ?, ?, ?)
    ''', (entity_name, relation, target_entity, additional_info))
    conn.commit()
    new_id = cursor.lastrowid
    conn.close()
    return {"status": "success", "id": new_id}

def query_knowledge_base(query: str):
    """Search for information in the knowledge base."""
    rows = query_db("SELECT * FROM knowledge_base WHERE entity_name LIKE ? OR relation LIKE ? OR target_entity LIKE ? OR additional_info LIKE ?", 
                   (f'%{query}%', f'%{query}%', f'%{query}%', f'%{query}%'))
    return [dict(row) for row in rows]

# AI Agent Logic
tools = [
    {
        "type": "function",
        "function": {
            "name": "get_customers",
            "description": "Get all customers in the database",
            "parameters": {"type": "object", "properties": {}}
        }
    },
    {
        "type": "function",
        "function": {
            "name": "search_customers",
            "description": "Search for customers by name, company, or notes",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "The search query"}
                },
                "required": ["query"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_urgent_follow_ups",
            "description": "Get customers who need a follow-up soon",
            "parameters": {"type": "object", "properties": {}}
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_customer_details",
            "description": "Get detailed information about a specific customer",
            "parameters": {
                "type": "object",
                "properties": {
                    "customer_id": {"type": "integer", "description": "The customer ID"}
                },
                "required": ["customer_id"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "add_to_knowledge_base",
            "description": "Add a new fact or piece of information to the knowledge base",
            "parameters": {
                "type": "object",
                "properties": {
                    "entity_name": {"type": "string", "description": "The subject (e.g., Alice Johnson or TechCorp)"},
                    "relation": {"type": "string", "description": "The relationship (e.g., prefers, uses, is located in)"},
                    "target_entity": {"type": "string", "description": "The object (e.g., Email, Salesforce, New York)"},
                    "additional_info": {"type": "string", "description": "Any extra context or notes"}
                },
                "required": ["entity_name", "relation", "target_entity"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "query_knowledge_base",
            "description": "Search for specific facts in the knowledge base",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "The search term"}
                },
                "required": ["query"]
            }
        }
    }
]

class ChatRequest(BaseModel):
    messages: List[dict]

class KnowledgeRequest(BaseModel):
    entity_name: str
    relation: str
    target_entity: str
    additional_info: str = ""

@app.post("/api/chat")
async def chat(request: ChatRequest):
    messages = request.messages
    
    if not any(m["role"] == "system" for m in messages):
        messages.insert(0, {
            "role": "system",
            "content": """You are a helpful sales assistant. Your goal is to help the salesperson manage their customers and reach out to them at the right time.
            You have access to a customer database and a knowledge base (knowledge graph style facts). 
            You can search, list, get details, and add new information to both.
            When asked who to reach out to, check for urgent follow-ups first.
            When drafting messages, use the customer's notes, company information, and knowledge base facts to make it personal and professional.
            Today's date is """ + datetime.now().strftime("%Y-%m-%d")
        })

    response = client.chat.completions.create(
        model="gpt-4-turbo-preview",
        messages=messages,
        tools=tools,
        tool_choice="auto"
    )

    response_message = response.choices[0].message
    tool_calls = response_message.tool_calls

    if tool_calls:
        messages.append(response_message)
        for tool_call in tool_calls:
            function_name = tool_call.function.name
            function_args = json.loads(tool_call.function.arguments)
            
            if function_name == "get_customers":
                content = get_customers()
            elif function_name == "search_customers":
                content = search_customers(function_args.get("query"))
            elif function_name == "get_urgent_follow_ups":
                content = get_urgent_follow_ups()
            elif function_name == "get_customer_details":
                content = get_customer_details(function_args.get("customer_id"))
            elif function_name == "add_to_knowledge_base":
                content = add_to_knowledge_base(
                    function_args.get("entity_name"),
                    function_args.get("relation"),
                    function_args.get("target_entity"),
                    function_args.get("additional_info", "")
                )
            elif function_name == "query_knowledge_base":
                content = query_knowledge_base(function_args.get("query"))
            else:
                content = {"error": "Unknown function"}

            messages.append({
                "tool_call_id": tool_call.id,
                "role": "tool",
                "name": function_name,
                "content": json.dumps(content)
            })
        
        final_response = client.chat.completions.create(
            model="gpt-4-turbo-preview",
            messages=messages
        )
        return JSONResponse(content={"message": final_response.choices[0].message.content})
    
    return JSONResponse(content={"message": response_message.content})

@app.post("/api/knowledge")
async def api_add_knowledge(request: KnowledgeRequest):
    result = add_to_knowledge_base(
        request.entity_name,
        request.relation,
        request.target_entity,
        request.additional_info
    )
    return JSONResponse(content=result)

@app.get("/", response_class=HTMLResponse)
async def get_root():
    with open("index.html", "r") as f:
        return f.read()

@app.get("/index.html", response_class=HTMLResponse)
async def get_index_html():
    with open("index.html", "r") as f:
        return f.read()

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
