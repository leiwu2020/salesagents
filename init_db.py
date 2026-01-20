import sqlite3
import json

def init_db():
    conn = sqlite3.connect('sales.db')
    cursor = conn.cursor()
    
    # Create customers table
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS customers (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        email TEXT NOT NULL,
        company TEXT,
        status TEXT,
        last_interaction TEXT,
        next_follow_up TEXT,
        notes TEXT,
        tags TEXT
    )
    ''')

    # Create knowledge_base table for structured/unstructured info
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS knowledge_base (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        entity_name TEXT NOT NULL,
        relation TEXT NOT NULL,
        target_entity TEXT NOT NULL,
        additional_info TEXT,
        created_at TEXT DEFAULT CURRENT_TIMESTAMP
    )
    ''')
    
    # Insert mock data if empty
    cursor.execute('SELECT COUNT(*) FROM customers')
    if cursor.fetchone()[0] == 0:
        # ... (keep existing customer data)
        pass

    # Insert mock knowledge base data
    cursor.execute('SELECT COUNT(*) FROM knowledge_base')
    if cursor.fetchone()[0] == 0:
        knowledge = [
            ('Alice Johnson', 'prefers', 'Email communication', 'Usually responds in the morning'),
            ('TechCorp', 'uses', 'Salesforce CRM', 'Integrating our tool via API'),
            ('StartupIO', 'is focusing on', 'Q1 expansion', 'Looking for enterprise-grade security'),
        ]
        cursor.executemany('''
        INSERT INTO knowledge_base (entity_name, relation, target_entity, additional_info)
        VALUES (?, ?, ?, ?)
        ''', knowledge)
        customers = [
            ('Alice Johnson', 'alice@techcorp.com', 'TechCorp', 'active', '2025-12-15T10:00:00', '2026-01-22T09:00:00', 'Interested in the new AI features. Last spoke about pricing tier upgrades.', 'high-value,enterprise'),
            ('Bob Smith', 'bob@startup.io', 'StartupIO', 'lead', '2026-01-05T14:30:00', None, 'Trial user. Showing high activity but hasn\'t converted to paid yet.', 'trial,urgent'),
            ('Charlie Davis', 'charlie@bigretail.com', 'Big Retail', 'churned', '2025-11-20T11:00:00', None, 'Left due to lack of specific integration. Worth checking back if we released it.', 'lost-deal'),
            ('Diana Prince', 'diana@amazon.com', 'Amazon', 'active', '2026-01-18T16:00:00', '2026-01-25T10:00:00', 'Requested a demo of the new dashboard next week.', 'key-account')
        ]
        cursor.executemany('''
        INSERT INTO customers (name, email, company, status, last_interaction, next_follow_up, notes, tags)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ''', customers)
        
    conn.commit()
    conn.close()

if __name__ == '__main__':
    init_db()
    print("Database initialized.")
