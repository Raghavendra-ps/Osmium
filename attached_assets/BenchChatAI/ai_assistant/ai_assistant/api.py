# Copyright (c) 2025, ERPNext and contributors
# For license information, please see license.txt

import json
import frappe
from frappe import _
from frappe.utils import now_datetime, cint
from ai_assistant.ai_assistant.services.ollama import OllamaService
from ai_assistant.ai_assistant.services.erpnext_exec import ERPNextExecutor
from ai_assistant.ai_assistant.services.schema import SchemaService


@frappe.whitelist()
def send_message(session_id, message, role="user"):
    """
    Send a chat message and get AI response.
    
    Args:
        session_id (str): Chat session ID
        message (str): Message content
        role (str): Message role ('user' or 'assistant')
    
    Returns:
        dict: Response with message ID and AI response
    """
    try:
        # Check permissions
        if not frappe.has_permission("AI Chat Message", "create"):
            frappe.throw(_("Not permitted to create chat messages"), frappe.PermissionError)
        
        # Validate session
        if session_id:
            if not frappe.db.exists("AI Chat Session", session_id):
                frappe.throw(_("Chat session not found"))
            
            # Check if user has access to this session
            session_user = frappe.db.get_value("AI Chat Session", session_id, "user")
            if session_user != frappe.session.user and not frappe.has_permission("AI Chat Session", "read"):
                frappe.throw(_("Not permitted to access this chat session"), frappe.PermissionError)
        else:
            # Create new session
            session_doc = frappe.get_doc({
                "doctype": "AI Chat Session",
                "title": f"Chat Session - {frappe.format(now_datetime(), 'datetime')}",
                "user": frappe.session.user,
                "session_start": now_datetime(),
                "status": "Active"
            })
            session_doc.insert()
            session_id = session_doc.name
        
        # Create user message
        user_msg = frappe.get_doc({
            "doctype": "AI Chat Message",
            "session": session_id,
            "role": "user",
            "content": message,
            "user": frappe.session.user,
            "timestamp": now_datetime()
        })
        user_msg.insert()
        
        # Generate AI response if role is user
        if role == "user":
            try:
                # Get settings
                settings = get_settings()
                
                # Get schema context for AI
                schema_context = SchemaService.get_schema_context()
                
                # Generate AI response using Ollama
                ollama = OllamaService(
                    url=settings.get("ollama_url", "http://localhost:11434"),
                    model=settings.get("model", "llama2")
                )
                
                # Analyze if this is a command
                command_analysis = ollama.analyze_command(message, schema_context)
                
                ai_response = ollama.generate_response(message, schema_context)
                
                # Create assistant message
                assistant_msg = frappe.get_doc({
                    "doctype": "AI Chat Message",
                    "session": session_id,
                    "role": "assistant",
                    "content": ai_response,
                    "user": frappe.session.user,
                    "timestamp": now_datetime()
                })
                
                # If command analysis indicates execution needed
                if command_analysis and command_analysis.get("isDestructive"):
                    assistant_msg.command_executed = command_analysis.get("command", "")
                    
                assistant_msg.insert()
                
                return {
                    "success": True,
                    "user_message_id": user_msg.name,
                    "assistant_message_id": assistant_msg.name,
                    "session_id": session_id,
                    "ai_response": ai_response,
                    "command_analysis": command_analysis
                }
                
            except Exception as ai_error:
                frappe.log_error(f"AI Response Error: {str(ai_error)}", "AI Assistant")
                
                # Create error response
                error_msg = frappe.get_doc({
                    "doctype": "AI Chat Message",
                    "session": session_id,
                    "role": "assistant",
                    "content": f"I encountered an error processing your request: {str(ai_error)}",
                    "user": frappe.session.user,
                    "timestamp": now_datetime(),
                    "is_error": 1
                })
                error_msg.insert()
                
                return {
                    "success": False,
                    "user_message_id": user_msg.name,
                    "assistant_message_id": error_msg.name,
                    "session_id": session_id,
                    "error": str(ai_error)
                }
        
        return {
            "success": True,
            "message_id": user_msg.name,
            "session_id": session_id
        }
        
    except frappe.PermissionError:
        raise
    except Exception as e:
        frappe.log_error(f"Send Message Error: {str(e)}", "AI Assistant")
        frappe.throw(_("Failed to send message: {0}").format(str(e)))


@frappe.whitelist()
def confirm_execute(message_id, command):
    """
    Confirm and execute a command from AI assistant.
    
    Args:
        message_id (str): AI Chat Message ID
        command (str): Command to execute
    
    Returns:
        dict: Execution result
    """
    try:
        # Check permissions
        if not frappe.has_permission("AI Chat Message", "write"):
            frappe.throw(_("Not permitted to execute commands"), frappe.PermissionError)
        
        # Get message
        message = frappe.get_doc("AI Chat Message", message_id)
        
        # Verify user has access
        if message.user != frappe.session.user and not frappe.has_permission("AI Chat Message", "read"):
            frappe.throw(_("Not permitted to access this message"), frappe.PermissionError)
        
        # Get settings
        settings = get_settings()
        
        # Check if safe mode is enabled and user confirmed
        if settings.get("safe_mode") and settings.get("confirm_destructive"):
            # Execute command
            executor = ERPNextExecutor(safe_mode=settings.get("safe_mode", True))
            result = executor.execute_command(command)
            
            # Update message with execution results
            message.command_executed = command
            message.command_result = json.dumps(result, indent=2)
            message.is_error = not result.get("success", False)
            message.execution_time = result.get("executionTime", 0)
            message.save()
            
            # Log if enabled
            if settings.get("log_commands"):
                frappe.logger("ai_assistant").info(f"Command executed: {command} | Result: {result}")
            
            return result
        else:
            frappe.throw(_("Command execution not allowed in current configuration"))
            
    except frappe.PermissionError:
        raise
    except Exception as e:
        frappe.log_error(f"Confirm Execute Error: {str(e)}", "AI Assistant")
        frappe.throw(_("Failed to execute command: {0}").format(str(e)))


@frappe.whitelist()
def clear_history(session_id=None):
    """
    Clear chat history for a session or all sessions for current user.
    
    Args:
        session_id (str, optional): Specific session to clear
    
    Returns:
        dict: Success status
    """
    try:
        # Check permissions
        if not frappe.has_permission("AI Chat Message", "delete"):
            frappe.throw(_("Not permitted to delete chat messages"), frappe.PermissionError)
        
        if session_id:
            # Clear specific session
            if not frappe.db.exists("AI Chat Session", session_id):
                frappe.throw(_("Chat session not found"))
            
            # Check access
            session_user = frappe.db.get_value("AI Chat Session", session_id, "user")
            if session_user != frappe.session.user and not frappe.has_permission("AI Chat Session", "delete"):
                frappe.throw(_("Not permitted to clear this session"), frappe.PermissionError)
            
            # Delete messages
            frappe.db.delete("AI Chat Message", {"session": session_id})
            
            # Update session
            frappe.db.set_value("AI Chat Session", session_id, {
                "message_count": 0,
                "session_end": now_datetime(),
                "status": "Completed"
            })
            
            return {"success": True, "message": _("Session history cleared")}
        else:
            # Clear all sessions for current user
            user_sessions = frappe.get_all("AI Chat Session", 
                filters={"user": frappe.session.user}, 
                pluck="name")
            
            if user_sessions:
                frappe.db.delete("AI Chat Message", {"session": ["in", user_sessions]})
                frappe.db.set_value("AI Chat Session", {"name": ["in", user_sessions]}, {
                    "message_count": 0,
                    "session_end": now_datetime(),
                    "status": "Completed"
                })
            
            return {"success": True, "message": _("All chat history cleared")}
            
    except frappe.PermissionError:
        raise
    except Exception as e:
        frappe.log_error(f"Clear History Error: {str(e)}", "AI Assistant")
        frappe.throw(_("Failed to clear history: {0}").format(str(e)))


@frappe.whitelist()
def get_settings():
    """
    Get AI Assistant settings.
    
    Returns:
        dict: Current settings
    """
    try:
        # Check permissions - any authenticated user can read settings
        if frappe.session.user == "Guest":
            frappe.throw(_("Authentication required"), frappe.AuthenticationError)
        
        settings = frappe.get_single("AI Assistant Settings")
        
        return {
            "ollama_url": settings.ollama_url or "http://localhost:11434",
            "model": settings.model or "llama2",
            "safe_mode": settings.safe_mode,
            "confirm_destructive": settings.confirm_destructive,
            "log_commands": settings.log_commands
        }
        
    except Exception as e:
        frappe.log_error(f"Get Settings Error: {str(e)}", "AI Assistant")
        frappe.throw(_("Failed to get settings: {0}").format(str(e)))


@frappe.whitelist()
def update_settings(ollama_url=None, model=None, safe_mode=None, 
                   confirm_destructive=None, log_commands=None):
    """
    Update AI Assistant settings.
    
    Args:
        ollama_url (str, optional): Ollama server URL
        model (str, optional): AI model name
        safe_mode (bool, optional): Enable safe mode
        confirm_destructive (bool, optional): Confirm destructive operations
        log_commands (bool, optional): Log executed commands
    
    Returns:
        dict: Updated settings
    """
    try:
        # Check permissions - only System Manager can update settings
        if not frappe.has_permission("AI Assistant Settings", "write"):
            frappe.throw(_("Not permitted to update AI Assistant settings"), frappe.PermissionError)
        
        settings = frappe.get_single("AI Assistant Settings")
        
        # Update provided fields
        if ollama_url is not None:
            settings.ollama_url = ollama_url
        if model is not None:
            settings.model = model
        if safe_mode is not None:
            settings.safe_mode = cint(safe_mode)
        if confirm_destructive is not None:
            settings.confirm_destructive = cint(confirm_destructive)
        if log_commands is not None:
            settings.log_commands = cint(log_commands)
        
        settings.save()
        
        return get_settings()
        
    except frappe.PermissionError:
        raise
    except Exception as e:
        frappe.log_error(f"Update Settings Error: {str(e)}", "AI Assistant")
        frappe.throw(_("Failed to update settings: {0}").format(str(e)))


@frappe.whitelist()
def start_scan():
    """
    Start database schema scanning in background.
    
    Returns:
        dict: Scan status
    """
    try:
        # Check permissions - only System Manager can start scan
        if not frappe.has_permission("AI Assistant Settings", "write"):
            frappe.throw(_("Not permitted to start schema scan"), frappe.PermissionError)
        
        # Enqueue background job
        frappe.enqueue(
            "ai_assistant.ai_assistant.services.schema.scan_database_background",
            queue="default",
            timeout=600,  # 10 minutes
            job_name="ai_assistant_schema_scan"
        )
        
        return {
            "success": True,
            "message": _("Schema scan started in background")
        }
        
    except frappe.PermissionError:
        raise
    except Exception as e:
        frappe.log_error(f"Start Scan Error: {str(e)}", "AI Assistant")
        frappe.throw(_("Failed to start schema scan: {0}").format(str(e)))


@frappe.whitelist()
def get_schema():
    """
    Get cached database schema.
    
    Returns:
        dict: Schema information
    """
    try:
        # Check permissions - authenticated users can read schema
        if frappe.session.user == "Guest":
            frappe.throw(_("Authentication required"), frappe.AuthenticationError)
        
        schema_context = SchemaService.get_schema_context()
        
        return {
            "success": True,
            "schema": schema_context
        }
        
    except Exception as e:
        frappe.log_error(f"Get Schema Error: {str(e)}", "AI Assistant")
        frappe.throw(_("Failed to get schema: {0}").format(str(e)))


@frappe.whitelist()
def get_chat_sessions():
    """
    Get chat sessions for current user.
    
    Returns:
        list: List of chat sessions
    """
    try:
        if frappe.session.user == "Guest":
            frappe.throw(_("Authentication required"), frappe.AuthenticationError)
        
        sessions = frappe.get_all("AI Chat Session",
            filters={"user": frappe.session.user},
            fields=["name", "title", "status", "session_start", "session_end", "message_count"],
            order_by="session_start desc",
            limit=50
        )
        
        return {"success": True, "sessions": sessions}
        
    except Exception as e:
        frappe.log_error(f"Get Chat Sessions Error: {str(e)}", "AI Assistant")
        frappe.throw(_("Failed to get chat sessions: {0}").format(str(e)))


@frappe.whitelist()
def get_chat_messages(session_id):
    """
    Get chat messages for a session.
    
    Args:
        session_id (str): Chat session ID
    
    Returns:
        list: List of chat messages
    """
    try:
        if frappe.session.user == "Guest":
            frappe.throw(_("Authentication required"), frappe.AuthenticationError)
        
        # Check session exists and access
        if not frappe.db.exists("AI Chat Session", session_id):
            frappe.throw(_("Chat session not found"))
        
        session_user = frappe.db.get_value("AI Chat Session", session_id, "user")
        if session_user != frappe.session.user and not frappe.has_permission("AI Chat Session", "read"):
            frappe.throw(_("Not permitted to access this chat session"), frappe.PermissionError)
        
        messages = frappe.get_all("AI Chat Message",
            filters={"session": session_id},
            fields=["name", "role", "content", "timestamp", "command_executed", 
                   "command_result", "is_error", "execution_time"],
            order_by="timestamp asc"
        )
        
        return {"success": True, "messages": messages}
        
    except frappe.PermissionError:
        raise
    except Exception as e:
        frappe.log_error(f"Get Chat Messages Error: {str(e)}", "AI Assistant")
        frappe.throw(_("Failed to get chat messages: {0}").format(str(e)))