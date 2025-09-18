# Copyright (c) 2025, ERPNext and Contributors
# See license.txt

import frappe
import unittest


class TestAIAssistantSettings(unittest.TestCase):
	def test_validate_required_fields(self):
		"""Test that required fields are validated"""
		settings = frappe.new_doc("AI Assistant Settings")
		
		# Test validation for required fields
		with self.assertRaises(frappe.exceptions.ValidationError):
			settings.insert()
			
	def test_url_format_correction(self):
		"""Test that URL format is corrected automatically"""
		settings = frappe.new_doc("AI Assistant Settings")
		settings.ollama_url = "localhost:11434"
		settings.model = "llama2"
		settings.validate()
		
		self.assertTrue(settings.ollama_url.startswith("http://"))