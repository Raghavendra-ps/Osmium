# Copyright (c) 2025, ERPNext and contributors
# For license information, please see license.txt

import json
import re
import requests
import frappe
from typing import Dict, Any, Optional
from frappe import _
from frappe.utils import cint


class OllamaService:
    """
    Service class for interacting with Ollama API.
    
    Provides methods for generating AI responses and analyzing commands
    for the AI Assistant ERPNext application.
    """
    
    def __init__(self, url: str = "http://localhost:11434", model: str = "llama2", timeout: int = 30):
        """
        Initialize Ollama service.
        
        Args:
            url (str): Ollama server URL
            model (str): AI model name
            timeout (int): Request timeout in seconds
        """
        self.url = url.rstrip('/')
        self.model = model
        self.timeout = timeout
        self.session = requests.Session()
        
        # Configure session
        self.session.headers.update({
            'Content-Type': 'application/json',
            'User-Agent': 'ERPNext-AI-Assistant/1.0'
        })
    
    def generate_response(self, prompt: str, schema_context: str = "") -> str:
        """
        Generate AI response for given prompt.
        
        Args:
            prompt (str): User prompt/question
            schema_context (str): Database schema context for better responses
        
        Returns:
            str: AI generated response
        
        Raises:
            Exception: If API call fails or times out
        """
        try:
            # Build context-aware prompt
            system_prompt = self._build_system_prompt(schema_context)
            full_prompt = f"{system_prompt}\n\nUser: {prompt}\nAssistant:"
            
            payload = {
                "model": self.model,
                "prompt": full_prompt,
                "stream": False,
                "options": {
                    "temperature": 0.7,
                    "max_tokens": 1000,
                    "stop": ["User:", "Human:"]
                }
            }
            
            response = self.session.post(
                f"{self.url}/api/generate",
                json=payload,
                timeout=self.timeout
            )
            
            if response.status_code == 200:
                result = response.json()
                return result.get('response', '').strip()
            else:
                error_msg = f"Ollama API returned {response.status_code}: {response.text}"
                frappe.log_error(error_msg, "Ollama Service")
                raise Exception(f"Failed to generate response: {error_msg}")
                
        except requests.exceptions.Timeout:
            frappe.log_error("Ollama API timeout", "Ollama Service")
            raise Exception("AI service is taking too long to respond. Please try again.")
        except requests.exceptions.ConnectionError:
            frappe.log_error(f"Cannot connect to Ollama at {self.url}", "Ollama Service")
            raise Exception(f"Cannot connect to AI service at {self.url}. Please check if Ollama is running.")
        except requests.exceptions.RequestException as e:
            frappe.log_error(f"Ollama API request error: {str(e)}", "Ollama Service")
            raise Exception(f"AI service error: {str(e)}")
        except Exception as e:
            frappe.log_error(f"Ollama generate_response error: {str(e)}", "Ollama Service")
            raise
    
    def analyze_command(self, prompt: str, schema_context: str = "") -> Dict[str, Any]:
        """
        Analyze if a prompt contains a command that should be executed.
        
        Args:
            prompt (str): User prompt to analyze
            schema_context (str): Database schema context
        
        Returns:
            Dict[str, Any]: Command analysis with structure:
                {
                    "command": str,
                    "description": str,
                    "isDestructive": bool,
                    "requiresConfirmation": bool,
                    "category": str
                }
        """
        try:
            analysis_prompt = self._build_command_analysis_prompt(prompt, schema_context)
            
            payload = {
                "model": self.model,
                "prompt": analysis_prompt,
                "stream": False,
                "options": {
                    "temperature": 0.1,  # Lower temperature for more consistent JSON
                    "max_tokens": 500
                }
            }
            
            response = self.session.post(
                f"{self.url}/api/generate",
                json=payload,
                timeout=self.timeout
            )
            
            if response.status_code == 200:
                result = response.json()
                response_text = result.get('response', '').strip()
                
                # Extract JSON from response
                command_analysis = self.extract_json_from_response(response_text)
                
                # Validate and set defaults
                return self._validate_command_analysis(command_analysis)
            else:
                frappe.log_error(f"Command analysis API error: {response.status_code} - {response.text}", "Ollama Service")
                return self._default_command_analysis()
                
        except requests.exceptions.Timeout:
            frappe.log_error("Command analysis timeout", "Ollama Service")
            return self._default_command_analysis()
        except Exception as e:
            frappe.log_error(f"Command analysis error: {str(e)}", "Ollama Service")
            return self._default_command_analysis()
    
    def extract_json_from_response(self, response_text: str) -> Dict[str, Any]:
        """
        Extract JSON object from AI response text.
        
        Args:
            response_text (str): Raw AI response text
        
        Returns:
            Dict[str, Any]: Parsed JSON object
        """
        try:
            # Try to find JSON block in response
            json_patterns = [
                r'```json\s*(\{.*?\})\s*```',
                r'```\s*(\{.*?\})\s*```',
                r'(\{.*?\})',
                r'JSON:\s*(\{.*?\})'
            ]
            
            for pattern in json_patterns:
                match = re.search(pattern, response_text, re.DOTALL)
                if match:
                    json_str = match.group(1)
                    try:
                        return json.loads(json_str)
                    except json.JSONDecodeError:
                        continue
            
            # If no JSON found, try parsing the entire response
            return json.loads(response_text)
            
        except json.JSONDecodeError:
            # Return empty dict if JSON parsing fails
            frappe.log_error(f"Failed to parse JSON from response: {response_text}", "Ollama Service")
            return {}
        except Exception as e:
            frappe.log_error(f"JSON extraction error: {str(e)}", "Ollama Service")
            return {}
    
    def _build_system_prompt(self, schema_context: str) -> str:
        """Build system prompt with ERPNext context."""
        base_prompt = """You are an AI assistant for ERPNext, an open-source ERP system. You help users with:
1. Understanding their business data and reports
2. Writing database queries to extract information
3. Analyzing business processes and workflows
4. Suggesting best practices for ERPNext usage

Guidelines:
- Always prioritize data security and user permissions
- Suggest only safe, non-destructive operations
- When writing SQL queries, always include appropriate LIMIT clauses
- Focus on helping users understand their business data
- Be concise but comprehensive in your responses"""
        
        if schema_context:
            base_prompt += f"\n\nDatabase Schema Context:\n{schema_context}"
            
        return base_prompt
    
    def _build_command_analysis_prompt(self, prompt: str, schema_context: str) -> str:
        """Build prompt for command analysis."""
        analysis_prompt = f"""Analyze the following user request and determine if it contains a command that should be executed in ERPNext.

User Request: "{prompt}"

{schema_context and f"Database Schema: {schema_context[:1000]}" or ""}

Return a JSON object with this exact structure:
{{
    "command": "extracted command or empty string",
    "description": "brief description of what the command does",
    "isDestructive": false,
    "requiresConfirmation": false,
    "category": "query|report|analysis|other"
}}

Categories:
- query: Database SELECT queries
- report: Generate reports or summaries
- analysis: Data analysis or calculations
- other: General questions or non-command requests

Mark isDestructive as true ONLY for commands that modify data (INSERT, UPDATE, DELETE, CREATE, DROP, ALTER).
Mark requiresConfirmation as true for any potentially risky operations.

Example responses:
For "Show me all customers": {{"command": "SELECT * FROM `tabCustomer` LIMIT 100", "description": "List all customers", "isDestructive": false, "requiresConfirmation": false, "category": "query"}}

For "What is ERPNext?": {{"command": "", "description": "General question about ERPNext", "isDestructive": false, "requiresConfirmation": false, "category": "other"}}

Return only the JSON object:"""
        
        return analysis_prompt
    
    def _validate_command_analysis(self, analysis: Dict[str, Any]) -> Dict[str, Any]:
        """Validate and normalize command analysis result."""
        return {
            "command": str(analysis.get("command", "")),
            "description": str(analysis.get("description", "No description available")),
            "isDestructive": bool(analysis.get("isDestructive", False)),
            "requiresConfirmation": bool(analysis.get("requiresConfirmation", False)),
            "category": str(analysis.get("category", "other"))
        }
    
    def _default_command_analysis(self) -> Dict[str, Any]:
        """Return default command analysis when parsing fails."""
        return {
            "command": "",
            "description": "Unable to analyze command",
            "isDestructive": False,
            "requiresConfirmation": False,
            "category": "other"
        }
    
    def test_connection(self) -> bool:
        """
        Test connection to Ollama service.
        
        Returns:
            bool: True if connection successful, False otherwise
        """
        try:
            response = self.session.get(f"{self.url}/api/tags", timeout=5)
            return response.status_code == 200
        except Exception as e:
            frappe.log_error(f"Ollama connection test failed: {str(e)}", "Ollama Service")
            return False
    
    def get_available_models(self) -> list:
        """
        Get list of available models from Ollama.
        
        Returns:
            list: List of available model names
        """
        try:
            response = self.session.get(f"{self.url}/api/tags", timeout=10)
            if response.status_code == 200:
                data = response.json()
                models = data.get('models', [])
                return [model.get('name', '') for model in models if model.get('name')]
            else:
                return []
        except Exception as e:
            frappe.log_error(f"Failed to get available models: {str(e)}", "Ollama Service")
            return []


def get_ollama_service() -> OllamaService:
    """
    Get configured Ollama service instance.
    
    Returns:
        OllamaService: Configured service instance
    """
    try:
        settings = frappe.get_single("AI Assistant Settings")
        return OllamaService(
            url=settings.ollama_url or "http://localhost:11434",
            model=settings.model or "llama2",
            timeout=30
        )
    except Exception as e:
        frappe.log_error(f"Failed to get Ollama service: {str(e)}", "Ollama Service")
        # Return default configuration
        return OllamaService()