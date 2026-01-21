import sqlite3
import json

def init_db():
    conn = sqlite3.connect('sales.db')
    cursor = conn.cursor()
    
    # Create users table
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT UNIQUE NOT NULL,
        hashed_password TEXT NOT NULL,
        created_at TEXT DEFAULT CURRENT_TIMESTAMP
    )
    ''')

    # Create customers table
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS customers (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        name TEXT NOT NULL,
        email TEXT NOT NULL,
        company TEXT,
        status TEXT,
        last_interaction TEXT,
        next_follow_up TEXT,
        notes TEXT,
        tags TEXT,
        FOREIGN KEY (user_id) REFERENCES users (id)
    )
    ''')

    # Create knowledge_base table for structured/unstructured info
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS knowledge_base (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        entity_name TEXT NOT NULL,
        relation TEXT NOT NULL,
        target_entity TEXT NOT NULL,
        additional_info TEXT,
        created_at TEXT DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (user_id) REFERENCES users (id)
    )
    ''')
    
    # Insert mock user if empty
    cursor.execute('SELECT COUNT(*) FROM users')
    if cursor.fetchone()[0] == 0:
        # Password is 'password123' (pbkdf2_sha256)
        hashed_pw = "$pbkdf2-sha256$29000$yRljzJkzRgihtPYeo7RWSg$wE9CC1i.Gb5kQh7iK9CWcqPDq1coQDXwQO1XFA65GDc"
        cursor.execute('INSERT INTO users (username, hashed_password) VALUES (?, ?)', ('demo', hashed_pw))
    
    # Get the user id
    cursor.execute('SELECT id FROM users WHERE username = ?', ('demo',))
    user_id = cursor.fetchone()[0]

    # Insert mock data if empty
    cursor.execute('SELECT COUNT(*) FROM customers')
    if cursor.fetchone()[0] == 0:
        customers = [
            (user_id, 'Alice Johnson', 'alice@techcorp.com', 'TechCorp', 'active', '2025-12-15T10:00:00', '2026-01-22T09:00:00', 'Interested in the new AI features. Last spoke about pricing tier upgrades.', 'high-value,enterprise'),
            (user_id, 'Bob Smith', 'bob@startup.io', 'StartupIO', 'lead', '2026-01-05T14:30:00', None, 'Trial user. Showing high activity but hasn\'t converted to paid yet.', 'trial,urgent'),
            (user_id, 'Charlie Davis', 'charlie@bigretail.com', 'Big Retail', 'churned', '2025-11-20T11:00:00', None, 'Left due to lack of specific integration. Worth checking back if we released it.', 'lost-deal'),
            (user_id, 'Diana Prince', 'diana@amazon.com', 'Amazon', 'active', '2026-01-18T16:00:00', '2026-01-25T10:00:00', 'Requested a demo of the new dashboard next week.', 'key-account')
        ]
        cursor.executemany('''
        INSERT INTO customers (user_id, name, email, company, status, last_interaction, next_follow_up, notes, tags)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', customers)
        
    # Insert mock knowledge base data
    cursor.execute('SELECT COUNT(*) FROM knowledge_base')
    if cursor.fetchone()[0] == 0:
        knowledge = [
            (user_id, 'Alice Johnson', 'prefers', 'Email communication', 'Usually responds in the morning'),
            (user_id, 'TechCorp', 'uses', 'Salesforce CRM', 'Integrating our tool via API'),
            (user_id, 'StartupIO', 'is focusing on', 'Q1 expansion', 'Looking for enterprise-grade security'),
        ]
        cursor.executemany('''
        INSERT INTO knowledge_base (user_id, entity_name, relation, target_entity, additional_info)
        VALUES (?, ?, ?, ?, ?)
        ''', knowledge)
        
    conn.commit()
    conn.close()

if __name__ == '__main__':
    init_db()
    print("Database initialized.")
