"""
Memory - Store conversations and user preferences
Uses SQLite for persistent storage
"""

import sqlite3
import json
import logging
from datetime import datetime
from pathlib import Path

logger = logging.getLogger(__name__)


class Memory:
    def __init__(self, db_path="memory.db"):
        self.db_path = db_path
        self.init_db()
    
    def init_db(self):
        """Initialize the database"""
        try:
            conn = sqlite3.connect(self.db_path)
            c = conn.cursor()
            
            # Conversations table
            c.execute('''
                CREATE TABLE IF NOT EXISTS conversations (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp TEXT,
                    role TEXT,
                    content TEXT
                )
            ''')
            
            # User preferences table
            c.execute('''
                CREATE TABLE IF NOT EXISTS preferences (
                    key TEXT PRIMARY KEY,
                    value TEXT
                )
            ''')

            # Task steps table - one row per ReAct loop iteration (Phase 2)
            c.execute('''
                CREATE TABLE IF NOT EXISTS task_steps (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    task_id TEXT,
                    timestamp TEXT,
                    step_number INTEGER,
                    goal TEXT,
                    thought TEXT,
                    tool TEXT,
                    args TEXT,
                    status TEXT,
                    observation TEXT
                )
            ''')

            conn.commit()
            conn.close()
            logger.info(f"Memory initialized: {self.db_path}")
        
        except Exception as e:
            logger.error(f"Memory init error: {e}")
    
    def add_interaction(self, role, content):
        """
        Add a conversation turn to memory
        
        Args:
            role: "user" or "assistant"
            content: The message
        """
        try:
            conn = sqlite3.connect(self.db_path)
            c = conn.cursor()
            
            timestamp = datetime.now().isoformat()
            c.execute('''
                INSERT INTO conversations (timestamp, role, content)
                VALUES (?, ?, ?)
            ''', (timestamp, role, content))
            
            conn.commit()
            conn.close()
        
        except Exception as e:
            logger.error(f"Error adding interaction: {e}")
    
    def log_task_step(
        self,
        task_id,
        step_number,
        goal,
        thought,
        tool,
        args,
        status,
        observation,
    ):
        """
        Log a single ReAct loop iteration to the task_steps table.

        Args:
            task_id: Unique id shared by all steps of one task run
            step_number: 1-based Think iteration index
            goal: The overall task goal
            thought: The LLM's reasoning for this step
            tool: Tool name chosen (or a marker like "done"/"__parse_error__")
            args: Tool arguments (dict) - stored as a JSON string
            status: Observation status ("success"/"error")
            observation: Human-readable result text from the ToolResult
        """
        try:
            conn = sqlite3.connect(self.db_path)
            c = conn.cursor()

            timestamp = datetime.now().isoformat()
            c.execute(
                '''
                INSERT INTO task_steps
                    (task_id, timestamp, step_number, goal, thought,
                     tool, args, status, observation)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''',
                (
                    task_id,
                    timestamp,
                    step_number,
                    goal,
                    thought,
                    tool,
                    json.dumps(args),
                    status,
                    observation,
                ),
            )

            conn.commit()
            conn.close()

        except Exception as e:
            logger.error(f"Error logging task step: {e}")

    def get_task_steps(self, task_id):
        """Fetch all logged steps for a task_id, in order. Used for inspection."""
        try:
            conn = sqlite3.connect(self.db_path)
            c = conn.cursor()
            c.execute(
                '''
                SELECT step_number, thought, tool, args, status, observation
                FROM task_steps WHERE task_id = ? ORDER BY id ASC
                ''',
                (task_id,),
            )
            rows = c.fetchall()
            conn.close()
            return rows
        except Exception as e:
            logger.error(f"Error fetching task steps: {e}")
            return []

    def get_conversation_history(self, last_n=10):
        """Get the last N conversation turns"""
        try:
            conn = sqlite3.connect(self.db_path)
            c = conn.cursor()
            
            c.execute('''
                SELECT role, content FROM conversations
                ORDER BY id DESC LIMIT ?
            ''', (last_n,))
            
            results = c.fetchall()
            conn.close()
            
            # Reverse to get chronological order
            return list(reversed(results))
        
        except Exception as e:
            logger.error(f"Error getting history: {e}")
            return []
    
    def get_context_for_llm(self, last_n=5):
        """Get conversation history formatted for LLM context"""
        history = self.get_conversation_history(last_n)
        
        context = "Previous conversation:\n"
        for role, content in history:
            context += f"{role}: {content}\n"
        
        return context
    
    def set_preference(self, key, value):
        """Store a user preference"""
        try:
            conn = sqlite3.connect(self.db_path)
            c = conn.cursor()
            
            c.execute('''
                INSERT OR REPLACE INTO preferences (key, value)
                VALUES (?, ?)
            ''', (key, str(value)))
            
            conn.commit()
            conn.close()
            logger.info(f"Preference set: {key} = {value}")
        
        except Exception as e:
            logger.error(f"Error setting preference: {e}")
    
    def get_preference(self, key, default=None):
        """Get a user preference"""
        try:
            conn = sqlite3.connect(self.db_path)
            c = conn.cursor()
            
            c.execute('SELECT value FROM preferences WHERE key = ?', (key,))
            result = c.fetchone()
            conn.close()
            
            return result[0] if result else default
        
        except Exception as e:
            logger.error(f"Error getting preference: {e}")
            return default
    
    def clear_history(self):
        """Clear conversation history"""
        try:
            conn = sqlite3.connect(self.db_path)
            c = conn.cursor()
            
            c.execute('DELETE FROM conversations')
            conn.commit()
            conn.close()
            logger.info("Conversation history cleared")
        
        except Exception as e:
            logger.error(f"Error clearing history: {e}")