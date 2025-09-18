# Copyright (c) 2025, ERPNext and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document


class AIAssistantSettings(Document):
	def validate(self):
		"""Validate AI Assistant Settings"""
		if not self.ollama_url:
			frappe.throw("Ollama URL is required")
		
		if not self.model:
			frappe.throw("AI Model is required")
			
		# Ensure URL format is correct
		if not self.ollama_url.startswith(('http://', 'https://')):
			self.ollama_url = f"http://{self.ollama_url}"