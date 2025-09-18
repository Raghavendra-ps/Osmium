# Copyright (c) 2025, ERPNext and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document
from frappe.utils import now_datetime


class AIChatSession(Document):
	def before_insert(self):
		"""Set session start time before inserting"""
		if not self.session_start:
			self.session_start = now_datetime()
			
		if not self.user:
			self.user = frappe.session.user
			
		if not self.title:
			self.title = f"Chat Session - {frappe.format(self.session_start, 'datetime')}"
	
	def on_update(self):
		"""Update message count when session is updated"""
		self.update_message_count()
	
	def update_message_count(self):
		"""Update the message count for this session"""
		message_count = frappe.db.count("AI Chat Message", {"session": self.name})
		if message_count != self.message_count:
			frappe.db.set_value("AI Chat Session", self.name, "message_count", message_count)
	
	def end_session(self):
		"""End the current session"""
		self.session_end = now_datetime()
		self.status = "Completed"
		self.save()