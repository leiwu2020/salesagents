import os
import sqlite3
import json
from datetime import datetime, timedelta
from typing import List, Optional
from fastapi import FastAPI, HTTPException, Request, Depends, status
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from pydantic import BaseModel
from openai import OpenAI
from dotenv import load_dotenv
from passlib.context import CryptContext
from jose import JWTError, jwt
from init_db import init_db

load_dotenv()

# JWT Configuration
SECRET_KEY = os.getenv("SECRET_KEY", "your-secret-key-for-jwt-keep-it-safe")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60 * 24  # 1 day

pwd_context = CryptContext(schemes=["pbkdf2_sha256"], deprecated="auto")
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="api/login")

app = FastAPI()
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

@app.on_event("startup")
async def startup_event():
    init_db()

# Models
class User(BaseModel):
    username: str

class UserInDB(User):
    hashed_password: str

class Token(BaseModel):
    access_token: str
    token_type: str

class TokenData(BaseModel):
    username: Optional[str] = None

class RegisterRequest(BaseModel):
    username: str
    password: str

class ChatRequest(BaseModel):
    messages: List[dict]

class KnowledgeRequest(BaseModel):
    entity_name: str
    relation: str
    target_entity: str
    additional_info: str = ""

# Database helpers
def query_db(query, args=(), one=False):
    conn = sqlite3.connect('sales.db')
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()
    cur.execute(query, args)
    rv = cur.fetchall()
    conn.close()
    return (rv[0] if rv else None) if one else rv

def execute_db(query, args=()):
    conn = sqlite3.connect('sales.db')
    cur = conn.cursor()
    cur.execute(query, args)
    conn.commit()
    lastrowid = cur.lastrowid
    conn.close()
    return lastrowid

# Auth Helpers
def verify_password(plain_password, hashed_password):
    return pwd_context.verify(plain_password, hashed_password)

def get_password_hash(password):
    return pwd_context.hash(password)

def create_access_token(data: dict, expires_delta: Optional[timedelta] = None):
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=15)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt

async def get_current_user(token: str = Depends(oauth2_scheme)):
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        username: str = payload.get("sub")
        if username is None:
            raise credentials_exception
        token_data = TokenData(username=username)
    except JWTError:
        raise credentials_exception
    user = query_db("SELECT id, username FROM users WHERE username = ?", (token_data.username,), one=True)
    if user is None:
        raise credentials_exception
    return dict(user)

# Tool Functions with user_id
def get_customers(user_id: int):
    rows = query_db('SELECT * FROM customers WHERE user_id = ?', (user_id,))
    return [dict(row) for row in rows]

def search_customers(user_id: int, query: str):
    rows = query_db("SELECT * FROM customers WHERE user_id = ? AND (name LIKE ? OR company LIKE ? OR notes LIKE ?)", 
                   (user_id, f'%{query}%', f'%{query}%', f'%{query}%'))
    return [dict(row) for row in rows]

def get_urgent_follow_ups(user_id: int):
    now = datetime.now().isoformat()
    two_days_later = (datetime.now() + timedelta(days=2)).isoformat()
    rows = query_db("SELECT * FROM customers WHERE user_id = ? AND next_follow_up IS NOT NULL AND next_follow_up <= ?", 
                   (user_id, two_days_later))
    return [dict(row) for row in rows]

def get_customer_details(user_id: int, customer_id: int):
    row = query_db("SELECT * FROM customers WHERE user_id = ? AND id = ?", (user_id, customer_id), one=True)
    return dict(row) if row else None

def add_to_knowledge_base(user_id: int, entity_name: str, relation: str, target_entity: str, additional_info: str = ""):
    new_id = execute_db('''
        INSERT INTO knowledge_base (user_id, entity_name, relation, target_entity, additional_info)
        VALUES (?, ?, ?, ?, ?)
    ''', (user_id, entity_name, relation, target_entity, additional_info))
    return {"status": "success", "id": new_id}

def query_knowledge_base(user_id: int, query: str):
    rows = query_db("SELECT * FROM knowledge_base WHERE user_id = ? AND (entity_name LIKE ? OR relation LIKE ? OR target_entity LIKE ? OR additional_info LIKE ?)", 
                   (user_id, f'%{query}%', f'%{query}%', f'%{query}%', f'%{query}%'))
    return [dict(row) for row in rows]

def add_customer(user_id: int, name: str, email: str, company: str = "", status: str = "lead", notes: str = "", next_follow_up: str = None):
    """Add a new customer to the database."""
    new_id = execute_db('''
        INSERT INTO customers (user_id, name, email, company, status, notes, next_follow_up, last_interaction)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    ''', (user_id, name, email, company, status, notes, next_follow_up, datetime.now().isoformat()))
    return {"status": "success", "id": new_id, "message": f"Customer {name} added successfully."}

# AI Tools Definition
def get_tools_definition():
    return [
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
                        "entity_name": {"type": "string", "description": "The subject"},
                        "relation": {"type": "string", "description": "The relationship"},
                        "target_entity": {"type": "string", "description": "The object"},
                        "additional_info": {"type": "string", "description": "Extra context"}
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
        },
        {
            "type": "function",
            "function": {
                "name": "add_customer",
                "description": "Add a new customer to the database",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "name": {"type": "string", "description": "Customer name"},
                        "email": {"type": "string", "description": "Customer email"},
                        "company": {"type": "string", "description": "Company name"},
                        "status": {"type": "string", "description": "Status (lead, active, churned)", "enum": ["lead", "active", "churned"]},
                        "notes": {"type": "string", "description": "Initial notes about the customer"},
                        "next_follow_up": {"type": "string", "description": "ISO date for next follow up (optional)"}
                    },
                    "required": ["name", "email"]
                }
            }
        }
    ]

# Auth Routes
@app.post("/api/register")
async def register(req: RegisterRequest):
    user = query_db("SELECT id FROM users WHERE username = ?", (req.username,), one=True)
    if user:
        throw_error = HTTPException(status_code=400, detail="Username already registered")
        raise throw_error
    
    hashed_password = get_password_hash(req.password)
    execute_db("INSERT INTO users (username, hashed_password, is_approved) VALUES (?, ?, ?)", (req.username, hashed_password, 0))
    
    # Send registration info for approval (Logging to console for now)
    # In production, replace this with an actual email service like SendGrid or SES
    print(f"NOTIFICATION: New registration for '{req.username}'. Approval request sent to adamresearch28@gmail.com")
    
    return {"status": "success", "message": "Registration submitted. Waiting for approval."}

@app.post("/api/login")
async def login(form_data: OAuth2PasswordRequestForm = Depends()):
    user = query_db("SELECT * FROM users WHERE username = ?", (form_data.username,), one=True)
    if not user or not verify_password(form_data.password, user["hashed_password"]):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    if not user["is_approved"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Account pending approval. Please contact administrator.",
        )

    access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        data={"sub": user["username"]}, expires_delta=access_token_expires
    )
    return {"access_token": access_token, "token_type": "bearer"}

# Protected Chat and Knowledge Routes
@app.post("/api/chat")
async def chat(request: ChatRequest, current_user: dict = Depends(get_current_user)):
    try:
        messages = request.messages
        user_id = current_user["id"]
        
        if not any(m["role"] == "system" for m in messages):
            messages.insert(0, {
                "role": "system",
                "content": f"""You are a helpful sales assistant for user {current_user['username']}.
                You have access to their customer database and knowledge base (knowledge graph).
                
                CRITICAL RULES:
                1. NEVER rely on your memory for customer lists or specific facts. ALWAYS call the appropriate tool (`get_customers`, `search_customers`, `query_knowledge_base`) to get the most up-to-date information from the database when asked.
                2. When the user mentions a new fact about a customer, company, or relationship, IMMEDIATELY use the `add_to_knowledge_base` tool to record it.
                3. When asked to "list" or "show" customers, ALWAYS call `get_customers` to ensure you see newly added records.
                
                Today's date is {datetime.now().strftime("%Y-%m-%d")}.
                Always ensure you are only accessing and managing data for the current user."""
            })

        response = client.chat.completions.create(
            model="gpt-4-turbo-preview",
            messages=messages,
            tools=get_tools_definition(),
            tool_choice="auto"
        )

        response_message = response.choices[0].message
        tool_calls = response_message.tool_calls

        if tool_calls:
            # Convert response_message to dict for the next request
            messages.append(response_message.model_dump(exclude_none=True))
            
            for tool_call in tool_calls:
                function_name = tool_call.function.name
                function_args = json.loads(tool_call.function.arguments)
                
                print(f"Executing tool: {function_name} with args: {function_args}")
                
                if function_name == "get_customers":
                    content = get_customers(user_id)
                elif function_name == "search_customers":
                    content = search_customers(user_id, function_args.get("query"))
                elif function_name == "get_urgent_follow_ups":
                    content = get_urgent_follow_ups(user_id)
                elif function_name == "get_customer_details":
                    content = get_customer_details(user_id, function_args.get("customer_id"))
                elif function_name == "add_to_knowledge_base":
                    content = add_to_knowledge_base(
                        user_id,
                        function_args.get("entity_name"),
                        function_args.get("relation"),
                        function_args.get("target_entity"),
                        function_args.get("additional_info", "")
                    )
                elif function_name == "query_knowledge_base":
                    content = query_knowledge_base(user_id, function_args.get("query"))
                elif function_name == "add_customer":
                    content = add_customer(
                        user_id,
                        function_args.get("name"),
                        function_args.get("email"),
                        function_args.get("company", ""),
                        function_args.get("status", "lead"),
                        function_args.get("notes", ""),
                        function_args.get("next_follow_up")
                    )
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
    except Exception as e:
        print(f"CHAT ERROR: {str(e)}")
        import traceback
        traceback.print_exc()
        return JSONResponse(
            status_code=500,
            content={"message": f"I'm sorry, I encountered an internal error: {str(e)}. Please check the logs."}
        )

@app.post("/api/knowledge")
async def api_add_knowledge(request: KnowledgeRequest, current_user: dict = Depends(get_current_user)):
    result = add_to_knowledge_base(
        current_user["id"],
        request.entity_name,
        request.relation,
        request.target_entity,
        request.additional_info
    )
    return JSONResponse(content=result)

@app.get("/api/me")
async def get_me(current_user: dict = Depends(get_current_user)):
    return current_user

@app.post("/api/admin/approve/{username}")
async def approve_user(username: str, admin_key: str):
    # This is a simple security check. In production, use a more robust method.
    if admin_key != os.getenv("ADMIN_KEY", "adam-secret-key-2026"):
        raise HTTPException(status_code=403, detail="Invalid admin key")
    
    user = query_db("SELECT id FROM users WHERE username = ?", (username,), one=True)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    execute_db("UPDATE users SET is_approved = 1 WHERE username = ?", (username,))
    return {"status": "success", "message": f"User {username} has been approved."}

# Static Routes
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
