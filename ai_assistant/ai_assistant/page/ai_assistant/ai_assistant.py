# Copyright (c) 2025, ERPNext and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.utils import now_datetime


class AIAssistantPage:
    """
    Server-side page controller for AI Assistant Desk page.
    
    Handles page configuration, permissions, and initialization.
    """
    
    def __init__(self):
        self.page_name = "ai_assistant"
        self.page_title = _("AI Assistant")
        self.icon = "fa fa-robot"
        
    def get_context(self):
        """
        Get page context and configuration.
        
        Returns:
            dict: Page context with configuration and initial data
        """
        # Check permissions
        self.check_permission()
        
        context = frappe._dict()
        context.page_title = self.page_title
        context.icon = self.icon
        context.user = frappe.session.user
        context.user_image = frappe.db.get_value("User", frappe.session.user, "user_image")
        context.full_name = frappe.utils.get_fullname(frappe.session.user)
        
        # Get current settings
        try:
            settings = frappe.get_single("AI Assistant Settings")
            context.settings = {
                "provider": settings.provider or "ollama",
                "ollama_url": settings.ollama_url or "http://localhost:11434",
                "ollama_model": settings.ollama_model or "llama2",
                "openai_model": settings.openai_model or "gpt-4o",
                "has_openai_key": bool(settings.openai_api_key),
                "safe_mode": settings.safe_mode,
                "confirm_destructive": settings.confirm_destructive,
                "confirm_sql_operations": settings.confirm_sql_operations,
                "log_commands": settings.log_commands
            }
        except Exception:
            # Provide defaults if settings not found
            context.settings = {
                "provider": "ollama",
                "ollama_url": "http://localhost:11434",
                "ollama_model": "llama2",
                "openai_model": "gpt-4o",
                "has_openai_key": False,
                "safe_mode": 1,
                "confirm_destructive": 1,
                "confirm_sql_operations": 1,
                "log_commands": 0
            }
        
        # Get recent chat sessions for the user
        try:
            context.recent_sessions = frappe.get_all("AI Chat Session",
                filters={"user": frappe.session.user, "status": "Active"},
                fields=["name", "title", "session_start", "message_count"],
                order_by="session_start desc",
                limit=10
            )
        except Exception:
            context.recent_sessions = []
        
        # Check user permissions
        context.can_manage_settings = frappe.has_permission("AI Assistant Settings", "write")
        context.can_create_sessions = frappe.has_permission("AI Chat Session", "create")
        context.can_send_messages = frappe.has_permission("AI Chat Message", "create")
        
        return context
    
    def check_permission(self):
        """
        Check if user has permission to access the AI Assistant page.
        
        Raises:
            frappe.PermissionError: If user doesn't have required permissions
        """
        if frappe.session.user == "Guest":
            frappe.throw(_("Please log in to access AI Assistant"), frappe.AuthenticationError)
        
        # Check if user can at least read AI Chat Sessions or Messages
        if not (frappe.has_permission("AI Chat Session", "read") or 
                frappe.has_permission("AI Chat Message", "read")):
            frappe.throw(_("You don't have permission to access AI Assistant"), 
                        frappe.PermissionError)
    
    @staticmethod
    def get_page_info():
        """
        Get static page information for registration.
        
        Returns:
            dict: Page registration info
        """
        return {
            "page_name": "ai_assistant",
            "page_title": _("AI Assistant"),
            "icon": "fa fa-robot",
            "single_page": True,
            "is_query_report": False
        }


def get_context(context=None):
    """
    ERPNext page context handler.
    
    Args:
        context (dict, optional): Existing context
        
    Returns:
        dict: Complete page context
    """
    page = AIAssistantPage()
    return page.get_context()


@frappe.whitelist()
def get_page_data():
    """
    Get page data for JavaScript initialization.
    
    Returns:
        dict: Page data including user info and permissions
    """
    try:
        page = AIAssistantPage()
        page.check_permission()
        
        # Get settings using the standardized get_settings function
        from ai_assistant.ai_assistant.api import get_settings
        try:
            settings_data = get_settings()
        except Exception:
            settings_data = {
                "provider": "ollama",
                "ollama_url": "http://localhost:11434",
                "ollama_model": "llama2",
                "has_openai_key": False,
                "openai_model": "gpt-5",
                "safe_mode": 1,
                "confirm_destructive": 1,
                "confirm_sql_operations": 1,
                "log_commands": 0
            }
        
        return {
            "success": True,
            "user": {
                "name": frappe.session.user,
                "full_name": frappe.utils.get_fullname(frappe.session.user),
                "image": frappe.db.get_value("User", frappe.session.user, "user_image")
            },
            "settings": settings_data,
            "permissions": {
                "can_manage_settings": frappe.has_permission("AI Assistant Settings", "write"),
                "can_create_sessions": frappe.has_permission("AI Chat Session", "create"),
                "can_send_messages": frappe.has_permission("AI Chat Message", "create")
            }
        }
    except Exception as e:
        frappe.log_error(f"Error getting page data: {str(e)}", "AI Assistant Page")
        return {
            "success": False,
            "error": str(e)
        }


@frappe.whitelist()
def initialize_session():
    """
    Initialize a new chat session.
    
    Returns:
        dict: Session creation result
    """
    try:
        from ai_assistant.ai_assistant.api import create_chat_session
        session = create_chat_session()
        return {
            "success": True,
            "session": session
        }
    except Exception as e:
        frappe.log_error(f"Error initializing session: {str(e)}", "AI Assistant Session")
        return {
            "success": False,
            "error": str(e)
        }
