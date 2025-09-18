#!/usr/bin/env python3
"""
Simple test server for ERPNext AI Assistant
Tests the core AI functionality without full ERPNext dependencies
"""

import os
import json
from flask import Flask, request, jsonify, render_template_string
from typing import Dict, Any

# Import our enhanced AI service
import sys
sys.path.append('ai_assistant/ai_assistant/services')

try:
    from ollama import AIService
except ImportError as e:
    print(f"Import error: {e}")
    # Create a simple fallback
    class AIService:
        def __init__(self, *args, **kwargs):
            self.provider = kwargs.get('provider', 'ollama')
            
        def generate_response(self, prompt, schema_context=""):
            return f"Echo: {prompt} (using {self.provider})"
            
        def analyze_command(self, prompt, schema_context=""):
            return {
                "isCommand": False,
                "command": "",
                "description": "Test response",
                "category": "other",
                "isDestructive": False
            }

app = Flask(__name__)

# Simple HTML template for testing
HTML_TEMPLATE = """
<!DOCTYPE html>
<html>
<head>
    <title>AI Assistant Test</title>
    <style>
        body { font-family: Arial, sans-serif; max-width: 800px; margin: 0 auto; padding: 20px; }
        .chat-box { border: 1px solid #ccc; height: 400px; overflow-y: auto; padding: 10px; margin: 10px 0; }
        .message { margin: 10px 0; padding: 10px; border-radius: 5px; }
        .user { background-color: #e3f2fd; text-align: right; }
        .assistant { background-color: #f1f8e9; }
        input[type="text"] { width: 70%; padding: 10px; }
        button { padding: 10px 20px; }
        .settings { background-color: #fff3e0; padding: 10px; margin: 10px 0; border-radius: 5px; }
    </style>
</head>
<body>
    <h1>🤖 AI Assistant Test Server</h1>
    
    <div class="settings">
        <h3>Settings</h3>
        <label>
            Provider: 
            <select id="provider">
                <option value="ollama">Ollama (Local)</option>
                <option value="openai">OpenAI</option>
            </select>
        </label>
        <label>
            Model: <input type="text" id="model" value="llama2" placeholder="Model name">
        </label>
        <button onclick="updateSettings()">Update Settings</button>
    </div>
    
    <div class="chat-box" id="chatBox">
        <div class="message assistant">
            <strong>AI Assistant:</strong> Hello! I'm ready to help you with ERPNext queries. What would you like to know?
        </div>
    </div>
    
    <div>
        <input type="text" id="messageInput" placeholder="Ask me anything about ERPNext..." onkeypress="if(event.key==='Enter') sendMessage()">
        <button onclick="sendMessage()">Send</button>
    </div>

    <script>
        function addMessage(sender, message) {
            const chatBox = document.getElementById('chatBox');
            const messageDiv = document.createElement('div');
            messageDiv.className = `message ${sender}`;
            messageDiv.innerHTML = `<strong>${sender === 'user' ? 'You' : 'AI Assistant'}:</strong> ${message}`;
            chatBox.appendChild(messageDiv);
            chatBox.scrollTop = chatBox.scrollHeight;
        }

        function sendMessage() {
            const input = document.getElementById('messageInput');
            const message = input.value.trim();
            if (!message) return;

            addMessage('user', message);
            input.value = '';

            // Send to backend
            fetch('/chat', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ message: message })
            })
            .then(response => response.json())
            .then(data => {
                if (data.success) {
                    addMessage('assistant', data.response);
                    if (data.command_analysis && data.command_analysis.isCommand) {
                        addMessage('assistant', `🔧 Command detected: ${data.command_analysis.description}`);
                    }
                } else {
                    addMessage('assistant', `Error: ${data.error}`);
                }
            })
            .catch(error => {
                addMessage('assistant', `Connection error: ${error.message}`);
            });
        }

        function updateSettings() {
            const provider = document.getElementById('provider').value;
            const model = document.getElementById('model').value;
            
            fetch('/settings', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ provider: provider, model: model })
            })
            .then(response => response.json())
            .then(data => {
                if (data.success) {
                    addMessage('assistant', `Settings updated: ${provider} with model ${model}`);
                } else {
                    addMessage('assistant', `Settings error: ${data.error}`);
                }
            });
        }
    </script>
</body>
</html>
"""

# Global AI service instance
ai_service = None

def initialize_ai_service(provider="ollama", model="llama2"):
    """Initialize AI service with given provider and model"""
    global ai_service
    try:
        if provider == "openai":
            ai_service = AIService(
                provider="openai",
                model=model if model.startswith('gpt-') else 'gpt-5',
                openai_api_key=os.environ.get("OPENAI_API_KEY")
            )
        else:
            ai_service = AIService(
                provider="ollama",
                url="http://localhost:11434",
                model=model or "llama2"
            )
        return True
    except Exception as e:
        print(f"Failed to initialize AI service: {e}")
        return False

@app.route('/')
def index():
    """Serve the test interface"""
    return render_template_string(HTML_TEMPLATE)

@app.route('/chat', methods=['POST'])
def chat():
    """Handle chat messages"""
    global ai_service
    
    try:
        data = request.json
        message = data.get('message', '').strip()
        
        if not message:
            return jsonify({"success": False, "error": "Empty message"})
        
        # Initialize AI service if not already done
        if ai_service is None:
            if not initialize_ai_service():
                return jsonify({"success": False, "error": "AI service not available"})
        
        # Generate response
        response = ai_service.generate_response(message, "")
        
        # Analyze if it's a command
        command_analysis = ai_service.analyze_command(message, "")
        
        return jsonify({
            "success": True,
            "response": response,
            "command_analysis": command_analysis
        })
        
    except Exception as e:
        return jsonify({"success": False, "error": str(e)})

@app.route('/settings', methods=['POST'])
def update_settings():
    """Update AI service settings"""
    try:
        data = request.json
        provider = data.get('provider', 'ollama')
        model = data.get('model', 'llama2')
        
        success = initialize_ai_service(provider, model)
        
        return jsonify({
            "success": success,
            "message": f"Settings updated to {provider} with model {model}" if success else "Failed to update settings"
        })
        
    except Exception as e:
        return jsonify({"success": False, "error": str(e)})

@app.route('/health')
def health():
    """Health check endpoint"""
    return jsonify({
        "status": "healthy",
        "ai_service": "available" if ai_service else "not_initialized"
    })

if __name__ == '__main__':
    print("🚀 Starting AI Assistant Test Server...")
    print("📝 This is a standalone test server for the ERPNext AI Assistant")
    print("🌐 Open http://localhost:5000 to test the AI functionality")
    
    # Initialize with default settings
    initialize_ai_service()
    
    app.run(host='0.0.0.0', port=5000, debug=True)