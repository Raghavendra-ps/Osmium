# Copyright (c) 2025, ERPNext and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document
from frappe.utils import now_datetime


class AIChatMessage(Document):
	def before_insert(self):
		"""Set default values before inserting"""
		if not self.timestamp:
			self.timestamp = now_datetime()
			
		if not self.user:
			self.user = frappe.session.user
			
		# Validate role
		if self.role not in ["user", "assistant"]:
			frappe.throw("Role must be either 'user' or 'assistant'")
	
	def after_insert(self):
		"""Update session message count after inserting new message"""
		if self.session:
			session_doc = frappe.get_doc("AI Chat Session", self.session)
			session_doc.update_message_count()
	
	def on_trash(self):
		"""Update session message count after deleting message"""
		if self.session:
			session_doc = frappe.get_doc("AI Chat Session", self.session)
			session_doc.update_message_count()