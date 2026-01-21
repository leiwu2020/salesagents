# SalesAgent Platform

An AI-powered sales assistant that helps you manage your customers, identifies who to reach out to, and drafts personalized messages.

[![Deploy to Render](https://render.com/images/deploy-to-render-button.svg)](https://render.com/deploy?repo=https://github.com/leiwu2020/salesagents)

## Features

- **Chat with Sales Assistant**: Ask questions about your customers and get instant answers.
- **Customer Database Integration**: The assistant has direct access to your customer records.
- **Urgent Follow-ups**: Automatically identifies customers who need attention based on follow-up dates.
- **Message Drafting**: Helps you draft professional and personalized outreach messages based on customer history and notes.

## Setup

1. **Install Dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

2. **Set up OpenAI API Key**:
   Create a `.env` file in the root directory and add your key:
   ```env
   OPENAI_API_KEY=your_api_key_here
   ```

3. **Initialize Database**:
   ```bash
   python3 init_db.py
   ```

4. **Run the Application**:
   ```bash
   python3 main.py
   ```

5. **Access the Website**:
   Open your browser and go to `http://localhost:8000`.

## Tech Stack

- **Backend**: FastAPI (Python)
- **Frontend**: React, Tailwind CSS, Lucide Icons (CDN)
- **Database**: SQLite
- **AI**: OpenAI GPT-4 with Tool Calling

## Admin: User Approval

Newly registered users are **pending approval** by default. To approve a user, you can send a POST request to the following endpoint:

`POST /api/admin/approve/{username}?admin_key=your_admin_key`

- Default `admin_key`: `adam-secret-key-2026` (You can change this in Render Environment Variables as `ADMIN_KEY`)
- You can use tools like `curl` or Postman to trigger this.
