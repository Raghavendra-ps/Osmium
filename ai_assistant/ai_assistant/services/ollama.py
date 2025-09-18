# Copyright (c) 2025, ERPNext and contributors
# For license information, please see license.txt

import json
import re
import requests
import os
from typing import Dict, Any, Optional

# Try to import frappe, but handle case where it's not available
try:
    import frappe
    from frappe import _
    from frappe.utils import cint
except ImportError:
    # Fallback for standalone testing
    frappe = None
    def _(text): return text
    def cint(val): return int(val) if val else 0

# Import OpenAI if available
try:
    from openai import OpenAI
except ImportError:
    OpenAI = None


class AIService:
    """
    Unified AI service class for interacting with both Ollama and OpenAI APIs.
    
    Provides methods for generating AI responses and analyzing commands
    for the AI Assistant ERPNext application.
    """
    
    def __init__(self, provider: str = "ollama", url: str = "http://localhost:11434", model: str = "llama2", timeout: int = 30, openai_api_key: str = None):
        """
        Initialize AI service.
        
        Args:
            provider (str): AI provider ('ollama' or 'openai')
            url (str): Ollama server URL (only used for Ollama)
            model (str): AI model name
            timeout (int): Request timeout in seconds
            openai_api_key (str): OpenAI API key (only used for OpenAI)
        """
        self.provider = provider.lower()
        self.url = url.rstrip('/') if url else ""
        self.model = model
        self.timeout = timeout
        
        if self.provider == "openai":
            # Initialize OpenAI client
            api_key = openai_api_key or os.environ.get("OPENAI_API_KEY")
            if not api_key:
                raise ValueError("OpenAI API key is required for OpenAI provider")
            if OpenAI is None:
                raise ImportError("OpenAI package not installed. Run: pip install openai")
            self.openai_client = OpenAI(api_key=api_key)
        else:
            # Initialize Ollama session
            self.session = requests.Session()
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
            if self.provider == "openai":
                return self._generate_openai_response(prompt, schema_context)
            else:
                return self._generate_ollama_response(prompt, schema_context)
        except Exception as e:
            error_msg = f"AI response generation failed: {str(e)}"
            if frappe:
                frappe.log_error(error_msg, "AI Service")
            raise Exception(error_msg)
    
    def _generate_ollama_response(self, prompt: str, schema_context: str = "") -> str:
        """Generate response using Ollama API."""
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
                if frappe:
                    frappe.log_error(error_msg, "Ollama Service")
                raise Exception(f"Failed to generate response: {error_msg}")
                
        except requests.exceptions.Timeout:
            if frappe:
                frappe.log_error("Ollama API timeout", "Ollama Service")
            raise Exception("AI service is taking too long to respond. Please try again.")
        except requests.exceptions.ConnectionError:
            if frappe:
                frappe.log_error(f"Cannot connect to Ollama at {self.url}", "Ollama Service")
            raise Exception(f"Cannot connect to AI service at {self.url}. Please check if Ollama is running.")
        except requests.exceptions.RequestException as e:
            if frappe:
                frappe.log_error(f"Ollama API request error: {str(e)}", "Ollama Service")
            raise Exception(f"AI service error: {str(e)}")
    
    def _generate_openai_response(self, prompt: str, schema_context: str = "") -> str:
        """Generate response using OpenAI API."""
        try:
            # Build context-aware system message
            system_prompt = self._build_system_prompt(schema_context)
            
            messages = [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": prompt}
            ]
            
            # the newest OpenAI model is "gpt-5" which was released August 7, 2025.
            # do not change this unless explicitly requested by the user
            model = self.model if self.model.startswith('gpt-') else 'gpt-5'
            
            response = self.openai_client.chat.completions.create(
                model=model,
                messages=messages,
                max_tokens=1000,
                timeout=self.timeout
            )
            
            return response.choices[0].message.content.strip()
        except Exception as e:
            if frappe:
                frappe.log_error(f"OpenAI API error: {str(e)}", "AI Service")
            raise Exception(f"OpenAI API error: {str(e)}")
    
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
            if self.provider == "openai":
                return self._analyze_command_openai(prompt, schema_context)
            else:
                return self._analyze_command_ollama(prompt, schema_context)
        except Exception as e:
            if frappe:
                frappe.log_error(f"Command analysis error: {str(e)}", "AI Service")
            return self._default_command_analysis()
    
    def _analyze_command_ollama(self, prompt: str, schema_context: str = "") -> Dict[str, Any]:
        """Analyze command using Ollama."""
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
            if frappe:
                frappe.log_error(f"Command analysis API error: {response.status_code} - {response.text}", "AI Service")
            return self._default_command_analysis()
    
    def _analyze_command_openai(self, prompt: str, schema_context: str = "") -> Dict[str, Any]:
        """Analyze command using OpenAI."""
        analysis_prompt = self._build_command_analysis_prompt(prompt, schema_context)
        
        messages = [
            {"role": "system", "content": analysis_prompt},
            {"role": "user", "content": prompt}
        ]
        
        # the newest OpenAI model is "gpt-5" which was released August 7, 2025.
        # do not change this unless explicitly requested by the user
        model = self.model if self.model.startswith('gpt-') else 'gpt-5'
        
        response = self.openai_client.chat.completions.create(
            model=model,
            messages=messages,
            response_format={"type": "json_object"},
            max_tokens=500,
            timeout=self.timeout
        )
        
        try:
            import json
            analysis_result = json.loads(response.choices[0].message.content)
            return self._validate_command_analysis(analysis_result)
        except Exception as e:
            if frappe:
                frappe.log_error(f"OpenAI analysis result parsing error: {str(e)}", "AI Service")
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
            if frappe:
                frappe.log_error(f"Failed to parse JSON from response: {response_text}", "AI Service")
            return {}
        except Exception as e:
            if frappe:
                frappe.log_error(f"JSON extraction error: {str(e)}", "AI Service")
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
        Test connection to AI service.
        
        Returns:
            bool: True if connection successful, False otherwise
        """
        try:
            if self.provider == "openai":
                # Test OpenAI connection with minimal request
                response = self.openai_client.chat.completions.create(
                    model="gpt-3.5-turbo",
                    messages=[{"role": "user", "content": "test"}],
                    max_tokens=1
                )
                return True
            else:
                # Test Ollama connection
                response = self.session.get(f"{self.url}/api/tags", timeout=5)
                return response.status_code == 200
        except Exception as e:
            if frappe:
                frappe.log_error(f"AI service connection test failed: {str(e)}", "AI Service")
            return False
    
    def get_available_models(self) -> list:
        """
        Get list of available models from AI service.
        
        Returns:
            list: List of available model names
        """
        try:
            if self.provider == "openai":
                # Return common OpenAI models
                return ["gpt-5", "gpt-4o", "gpt-4", "gpt-3.5-turbo"]
            else:
                # Get Ollama models
                response = self.session.get(f"{self.url}/api/tags", timeout=10)
                if response.status_code == 200:
                    data = response.json()
                    models = data.get('models', [])
                    return [model.get('name', '') for model in models if model.get('name')]
                else:
                    return []
        except Exception as e:
            if frappe:
                frappe.log_error(f"Failed to get available models: {str(e)}", "AI Service")
            return []


def get_ollama_service() -> AIService:
    """
    Get configured AI service instance.
    
    Returns:
        AIService: Configured service instance
    """
    try:
        if frappe:
            settings = frappe.get_single("AI Assistant Settings")
            return AIService(
                provider="ollama",
                url=settings.ollama_url or "http://localhost:11434",
                model=settings.model or "llama2",
                timeout=30
            )
        else:
            # Fallback for standalone testing
            return AIService()
    except Exception as e:
        if frappe:
            frappe.log_error(f"Failed to get AI service: {str(e)}", "AI Service")
        # Return default configuration
        return AIService()