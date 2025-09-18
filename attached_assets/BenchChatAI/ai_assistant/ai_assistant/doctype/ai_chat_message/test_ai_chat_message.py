# Copyright (c) 2025, ERPNext and Contributors
# See license.txt

import frappe
import unittest


class TestAIChatMessage(unittest.TestCase):
	def test_message_creation(self):
		"""Test that chat message is created with proper defaults"""
		# First create a session
		session = frappe.new_doc("AI Chat Session")
		session.title = "Test Session"
		session.user = "Administrator"
		session.insert()
		
		# Create a message
		message = frappe.new_doc("AI Chat Message")
		message.session = session.name
		message.content = "Test message"
		message.role = "user"
		message.insert()
		
		self.assertIsNotNone(message.timestamp)
		self.assertEqual(message.user, "Administrator")
		
		# Clean up
		message.delete()
		session.delete()
		
	def test_role_validation(self):
		"""Test that role validation works correctly"""
		message = frappe.new_doc("AI Chat Message")
		message.content = "Test message"
		message.role = "invalid_role"
		
		with self.assertRaises(frappe.exceptions.ValidationError):
			message.insert()