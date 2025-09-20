# Copyright (c) 2025, ERPNext and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document


class AIAssistantSettings(Document):
    def validate(self):
        """Validate AI Assistant Settings"""
        if not self.provider:
            frappe.throw("AI Provider is required")

        if self.provider == "ollama":
            if not self.ollama_url:
                frappe.throw("Ollama URL is required")
            if not self.ollama_model:
                frappe.throw("Ollama model is required when using Ollama provider")
            if not self.ollama_url.startswith(("http://", "https://")):
                self.ollama_url = f"http://{self.ollama_url}"

        elif self.provider == "openai":
            if not self.openai_model:
                frappe.throw("OpenAI model is required when using OpenAI provider")

