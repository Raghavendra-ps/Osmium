# Copyright (c) 2025, ERPNext and Contributors
# See license.txt

import frappe
import unittest
from frappe.utils import now_datetime


class TestAIChatSession(unittest.TestCase):
	def test_session_creation(self):
		"""Test that chat session is created with proper defaults"""
		session = frappe.new_doc("AI Chat Session")
		session.title = "Test Session"
		session.user = "Administrator"
		session.insert()
		
		self.assertIsNotNone(session.session_start)
		self.assertEqual(session.status, "Active")
		self.assertEqual(session.message_count, 0)
		
		# Clean up
		session.delete()
		
	def test_message_count_update(self):
		"""Test that message count is updated correctly"""
		session = frappe.new_doc("AI Chat Session")
		session.title = "Test Session"
		session.user = "Administrator"
		session.insert()
		
		# Create a message
		message = frappe.new_doc("AI Chat Message")
		message.session = session.name
		message.content = "Test message"
		message.role = "user"
		message.user = "Administrator"
		message.insert()
		
		# Check if session message count is updated
		session.reload()
		self.assertEqual(session.message_count, 1)
		
		# Clean up
		message.delete()
		session.delete()