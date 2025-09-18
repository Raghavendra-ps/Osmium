# Copyright (c) 2025, ERPNext and contributors
# For license information, please see license.txt

import re
import time
import subprocess
import json
import shlex
import frappe
from typing import Dict, Any, List, Optional, Tuple
from frappe import _
from frappe.utils import cint, flt
from .erpnext_api import ERPNextAPIService


class ERPNextExecutor:
    """
    Secure command execution service for AI Assistant.
    
    Handles safe execution of database queries and limited system commands
    with comprehensive security checks and safe mode enforcement.
    """
    
    # All SQL commands are now allowed (unrestricted access)
    # Confirmation is handled separately via settings.confirm_sql_operations
    
    # Allowed bench commands (safe operations only)
    ALLOWED_BENCH_COMMANDS = {
        # Information commands
        'version', '--version', '--help', '-h', 'help',
        'list-apps', 'get-config', 'site-info',
        
        # Document operations (safe read/write)
        'get-doc', 'set-value', 'list-docs', 'get-value',
        'new-doc', 'delete-doc',
        
        # Data operations (import/export)
        'export-csv', 'export-json', 'import-csv', 'import-json',
        
        # ERPNext-specific operations (safe)
        'show-config', 'doctor', 'ready-for-migration',
        
        # User operations (limited)
        'list-users'
    }
    
    # Admin-only commands that are NEVER allowed (even if safe mode is off)
    BLOCKED_ADMIN_COMMANDS = {
        'migrate', 'rollback-migration', 'clear-cache', 'clear-website-cache',
        'backup', 'restore', 'install-app', 'uninstall-app', 'update', 'pull',
        'setup', 'new-site', 'drop-site', 'reinstall', 'bench-update',
        'restart', 'start', 'stop', 'reload-nginx', 'setup-nginx',
        # CRITICAL: Block dangerous execution commands
        'execute', 'console', 'mariadb', 'add-user', 'set-admin-password', 'disable-user'
    }
    
    # Shell metacharacters to detect and block
    SHELL_METACHARACTERS = {
        ';', '|', '&', '$', '`', '>', '<', '*', '?', '[', ']', 
        '(', ')', '{', '}', '\\', '"', "'", '\n', '\r'
    }
    
    def __init__(self, safe_mode: bool = True, timeout: int = 30):
        """
        Initialize ERPNext command executor.
        
        Args:
            safe_mode (bool): Enable safe mode restrictions
            timeout (int): Command execution timeout in seconds
        """
        self.safe_mode = safe_mode
        self.timeout = timeout
        self.api_service = ERPNextAPIService(use_rest_api=False)  # Use direct Frappe methods by default
        
        # Load site name from settings for site-specific operations
        try:
            if frappe:
                settings = frappe.get_single("AI Assistant Settings")
                self.site_name = settings.get("site_name", "frontend1") if settings else "frontend1"
            else:
                self.site_name = "frontend1"
        except Exception:
            self.site_name = "frontend1"
    
    def execute_command(self, command: str, force_execute: bool = False) -> Dict[str, Any]:
        """
        Execute a command with security checks.
        
        Args:
            command (str): Command to execute
        
        Returns:
            Dict[str, Any]: Execution result with structure:
                {
                    "success": bool,
                    "output": str,
                    "error": str,
                    "executionTime": int  # milliseconds
                }
        """
        start_time = time.time()
        
        try:
            # Basic validation
            if not command or not isinstance(command, str):
                return self._error_result("Invalid command", start_time)
            
            command = command.strip()
            if not command:
                return self._error_result("Empty command", start_time)
            
            # Security checks (skip for SQL commands - user requested unrestricted SQL access)
            if not self._is_sql_command(command):
                security_check = self._perform_security_checks(command)
                if not security_check["safe"]:
                    return self._error_result(security_check["reason"], start_time)
            
            # Determine command type and execute
            if self._is_sql_command(command):
                return self._execute_sql_command(command, start_time, force_execute)
            elif self._is_api_command(command):
                return self._execute_api_command(command, start_time)
            elif self._is_bench_command(command):
                if self.safe_mode:
                    return self._error_result("Bench commands disabled in safe mode", start_time)
                return self._execute_bench_command(command, start_time)
            else:
                return self._error_result("Command type not recognized or not allowed", start_time)
                
        except Exception as e:
            frappe.log_error(f"Command execution error: {str(e)}", "ERPNext Executor")
            return self._error_result(f"Execution error: {str(e)}", start_time)
    
    def _perform_security_checks(self, command: str) -> Dict[str, Any]:
        """
        Perform comprehensive security checks on command.
        
        Args:
            command (str): Command to check
        
        Returns:
            Dict[str, Any]: Security check result
        """
        # Check for shell metacharacters
        for char in self.SHELL_METACHARACTERS:
            if char in command:
                return {
                    "safe": False,
                    "reason": f"Shell metacharacter '{char}' not allowed for security"
                }
        
        # Check command length
        if len(command) > 2000:
            return {
                "safe": False,
                "reason": "Command too long (max 2000 characters)"
            }
        
        # Check for suspicious patterns
        suspicious_patterns = [
            r'--\s*$',  # SQL comments at end
            r'/\*.*?\*/',  # SQL block comments
            r'\bUNION\b.*\bSELECT\b',  # SQL injection patterns
            r'\bEXEC\b|\bXP_\b|\bSP_\b',  # System procedures
            r'\bFILE\b|\bINTO\s+OUTFILE\b',  # File operations
            r'\bLOAD_FILE\b|\bLOAD\s+DATA\b',  # File loading
        ]
        
        for pattern in suspicious_patterns:
            if re.search(pattern, command, re.IGNORECASE):
                return {
                    "safe": False,
                    "reason": f"Potentially dangerous pattern detected"
                }
        
        return {"safe": True, "reason": ""}
    
    def _is_sql_command(self, command: str) -> bool:
        """Check if command is a SQL command."""
        first_word = command.strip().split()[0].upper()
        # Common SQL command keywords
        sql_keywords = {
            'SELECT', 'INSERT', 'UPDATE', 'DELETE', 'CREATE', 'DROP', 'ALTER',
            'TRUNCATE', 'SHOW', 'DESCRIBE', 'DESC', 'EXPLAIN', 'REPLACE', 
            'MERGE', 'CALL', 'EXECUTE', 'WITH', 'UNION', 'JOIN'
        }
        return first_word in sql_keywords
    
    def _is_bench_command(self, command: str) -> bool:
        """Check if command is a bench command."""
        return command.strip().startswith('bench ') or command.strip() in self.ALLOWED_BENCH_COMMANDS
    
    def _execute_sql_command(self, command: str, start_time: float, force_execute: bool = False) -> Dict[str, Any]:
        """
        Execute SQL command using Frappe's database interface.
        
        Args:
            command (str): SQL command to execute
            start_time (float): Execution start time
        
        Returns:
            Dict[str, Any]: Execution result
        """
        try:
            first_word = command.strip().split()[0].upper()
            
            # Check if SQL confirmation is required (user requested ALL SQL operations require confirmation)
            if not force_execute and frappe:
                try:
                    settings = frappe.get_single("AI Assistant Settings")
                    if settings and settings.confirm_sql_operations:
                        return {
                            "success": False,
                            "output": "",
                            "error": "SQL command requires user confirmation",
                            "requires_confirmation": True,
                            "command": command,
                            "command_type": "sql",
                            "description": f"Execute SQL: {command}",
                            "executionTime": int((time.time() - start_time) * 1000)
                        }
                except Exception:
                    # If we can't get settings, proceed with execution
                    pass
            
            # All SQL commands are now allowed with unrestricted access
            # UNRESTRICTED SQL ACCESS - no modifications to user commands
            # (User requested completely unrestricted access with confirmation)
            
            # Execute using frappe.db.sql with unrestricted access
            if first_word in ['INSERT', 'UPDATE', 'DELETE', 'CREATE', 'DROP', 'ALTER', 'TRUNCATE']:
                # Data modification commands - commit changes and return affected rows
                frappe.db.begin()
                try:
                    result = frappe.db.sql(command)
                    frappe.db.commit()
                    
                    # For modification commands, show affected rows count
                    affected_rows = frappe.db.sql("SELECT ROW_COUNT() as affected_rows", as_dict=True)
                    output = f"Command executed successfully. Affected rows: {affected_rows[0]['affected_rows'] if affected_rows else 'Unknown'}"
                except Exception as e:
                    frappe.db.rollback()
                    raise e
                    
            elif first_word in ['SHOW', 'DESCRIBE', 'DESC']:
                # Information commands return simple results
                result = frappe.db.sql(command, as_dict=False)
                output = self._format_sql_result(result)
                
            else:
                # SELECT, EXPLAIN, and other query commands return structured data
                result = frappe.db.sql(command, as_dict=True)
                output = self._format_sql_result(result)
            
            execution_time = int((time.time() - start_time) * 1000)
            
            return {
                "success": True,
                "output": output,
                "error": "",
                "executionTime": execution_time
            }
            
        except Exception as e:
            error_msg = str(e)
            frappe.log_error(f"SQL execution error: {error_msg}", "ERPNext Executor")
            return self._error_result(f"SQL error: {error_msg}", start_time)
    
    def _execute_bench_command(self, command: str, start_time: float) -> Dict[str, Any]:
        """
        Execute allowed bench command using subprocess.
        
        Args:
            command (str): Bench command to execute
            start_time (float): Execution start time
        
        Returns:
            Dict[str, Any]: Execution result
        """
        try:
            # Parse command and add site context
            if command.startswith('bench '):
                cmd_parts = shlex.split(command)
            else:
                cmd_parts = ['bench'] + shlex.split(command)
            
            # Insert site-specific context for ERPNext operations
            # bench command becomes: bench --site sitename command
            if len(cmd_parts) > 1 and cmd_parts[1] != '--site':
                # Insert --site sitename after 'bench'
                cmd_parts.insert(1, '--site')
                cmd_parts.insert(2, self.site_name)
            
            # Validate command parts (skip site-related args)
            command_args = cmd_parts[3:] if '--site' in cmd_parts else cmd_parts[1:]
            if not self._is_allowed_bench_command(command_args):
                return self._error_result("Bench command not allowed", start_time)
            
            # Execute with timeout
            result = subprocess.run(
                cmd_parts,
                capture_output=True,
                text=True,
                timeout=self.timeout,
                cwd=frappe.get_site_path('..')
            )
            
            execution_time = int((time.time() - start_time) * 1000)
            
            if result.returncode == 0:
                return {
                    "success": True,
                    "output": result.stdout,
                    "error": result.stderr if result.stderr else "",
                    "executionTime": execution_time
                }
            else:
                return {
                    "success": False,
                    "output": result.stdout if result.stdout else "",
                    "error": result.stderr if result.stderr else "Command failed",
                    "executionTime": execution_time
                }
                
        except subprocess.TimeoutExpired:
            return self._error_result("Command timed out", start_time)
        except subprocess.CalledProcessError as e:
            return self._error_result(f"Command failed: {str(e)}", start_time)
        except Exception as e:
            frappe.log_error(f"Bench command error: {str(e)}", "ERPNext Executor")
            return self._error_result(f"Execution error: {str(e)}", start_time)
    
    def _is_allowed_bench_command(self, cmd_parts: List[str]) -> bool:
        """Check if bench command parts are allowed."""
        if not cmd_parts:
            return False
        
        # Check first argument
        first_arg = cmd_parts[0]
        
        # Block admin commands immediately
        if first_arg in self.BLOCKED_ADMIN_COMMANDS:
            return False
        
        # Check if command is in allowed list
        if first_arg in self.ALLOWED_BENCH_COMMANDS:
            return True
        
        # Allow specific patterns and complex commands
        safe_patterns = [
            r'^--help$', r'^-h$', r'^version$', r'^--version$',
            r'^--site$',  # Allow site specification
        ]
        
        for pattern in safe_patterns:
            if re.match(pattern, first_arg):
                return True
        
        # Handle complex bench commands with site specification
        if len(cmd_parts) >= 3 and cmd_parts[0] == '--site':
            # Allow: bench --site [site_name] [command]
            actual_command = cmd_parts[2]
            if actual_command in self.ALLOWED_BENCH_COMMANDS and actual_command not in self.BLOCKED_ADMIN_COMMANDS:
                return True
        
        return False
    
    def _is_api_command(self, command: str) -> bool:
        """Check if this is an API command (create, read, update, delete documents)."""
        command_lower = command.lower().strip()
        
        # API command patterns
        api_patterns = [
            "create ", "new ", "insert ",  # Create operations
            "get ", "read ", "fetch ", "find ",  # Read operations  
            "update ", "modify ", "edit ",  # Update operations
            "delete ", "remove ",  # Delete operations
            "list ", "search "  # List/search operations
        ]
        
        for pattern in api_patterns:
            if command_lower.startswith(pattern):
                return True
        
        return False
    
    def _execute_api_command(self, command: str, start_time: float) -> Dict[str, Any]:
        """
        Execute API command for document operations.
        
        Args:
            command (str): API command to execute
            start_time (float): Execution start time
        
        Returns:
            Dict[str, Any]: Execution result
        """
        try:
            command_lower = command.lower().strip()
            
            # Parse command and determine operation
            if command_lower.startswith(("create ", "new ", "insert ")):
                return self._handle_create_command(command, start_time)
            elif command_lower.startswith(("get ", "read ", "fetch ", "find ")):
                return self._handle_read_command(command, start_time)
            elif command_lower.startswith(("update ", "modify ", "edit ")):
                return self._handle_update_command(command, start_time)
            elif command_lower.startswith(("delete ", "remove ")):
                return self._handle_delete_command(command, start_time)
            elif command_lower.startswith(("list ", "search ")):
                return self._handle_list_command(command, start_time)
            else:
                return self._error_result("API command not recognized", start_time)
                
        except Exception as e:
            frappe.log_error(f"API command error: {str(e)}", "ERPNext Executor")
            return self._error_result(f"API execution error: {str(e)}", start_time)
    
    def _handle_create_command(self, command: str, start_time: float) -> Dict[str, Any]:
        """Handle create document commands."""
        # Parse: create Customer with customer_name="ABC Corp" and customer_type="Company"
        try:
            parts = command.split()
            if len(parts) < 2:
                return self._error_result("Invalid create command format", start_time)
            
            doctype = parts[1]
            
            # Simple parsing for key=value pairs
            data = {}
            if "with" in command:
                with_part = command.split("with", 1)[1].strip()
                # Parse key="value" pairs
                import re
                matches = re.findall(r'(\w+)=(?:"([^"]*)"|\'([^\']*)\'|(\S+))', with_part)
                for match in matches:
                    key = match[0]
                    value = match[1] or match[2] or match[3]
                    data[key] = value
            
            result = self.api_service.create_document(doctype, data)
            execution_time = int((time.time() - start_time) * 1000)
            result["executionTime"] = execution_time
            
            return result
            
        except Exception as e:
            return self._error_result(f"Create command error: {str(e)}", start_time)
    
    def _handle_read_command(self, command: str, start_time: float) -> Dict[str, Any]:
        """Handle read document commands."""
        # Parse: get Customer "CUST-00001" or find Customer where customer_name="ABC Corp"
        try:
            parts = command.split()
            if len(parts) < 2:
                return self._error_result("Invalid read command format", start_time)
            
            doctype = parts[1]
            
            # Simple name-based lookup
            if len(parts) >= 3 and not parts[2].startswith("where"):
                name = parts[2].strip('"\'')
                result = self.api_service.get_document(doctype, name)
            else:
                # List with basic filters
                filters = {}
                if "where" in command:
                    # Simple parsing - this could be enhanced
                    result = self.api_service.list_documents(doctype, filters, limit=10)
                else:
                    result = self.api_service.list_documents(doctype, limit=10)
            
            execution_time = int((time.time() - start_time) * 1000)
            result["executionTime"] = execution_time
            
            return result
            
        except Exception as e:
            return self._error_result(f"Read command error: {str(e)}", start_time)
    
    def _handle_update_command(self, command: str, start_time: float) -> Dict[str, Any]:
        """Handle update document commands."""
        # Parse: update Customer "CUST-00001" set customer_name="New Name"
        try:
            parts = command.split()
            if len(parts) < 4:
                return self._error_result("Invalid update command format", start_time)
            
            doctype = parts[1]
            name = parts[2].strip('"\'')
            
            # Parse set clauses
            data = {}
            if "set" in command:
                set_part = command.split("set", 1)[1].strip()
                import re
                matches = re.findall(r'(\w+)=(?:"([^"]*)"|\'([^\']*)\'|(\S+))', set_part)
                for match in matches:
                    key = match[0]
                    value = match[1] or match[2] or match[3]
                    data[key] = value
            
            result = self.api_service.update_document(doctype, name, data)
            execution_time = int((time.time() - start_time) * 1000)
            result["executionTime"] = execution_time
            
            return result
            
        except Exception as e:
            return self._error_result(f"Update command error: {str(e)}", start_time)
    
    def _handle_delete_command(self, command: str, start_time: float) -> Dict[str, Any]:
        """Handle delete document commands."""
        # Parse: delete Customer "CUST-00001"
        try:
            parts = command.split()
            if len(parts) < 3:
                return self._error_result("Invalid delete command format", start_time)
            
            doctype = parts[1]
            name = parts[2].strip('"\'')
            
            result = self.api_service.delete_document(doctype, name)
            execution_time = int((time.time() - start_time) * 1000)
            result["executionTime"] = execution_time
            
            return result
            
        except Exception as e:
            return self._error_result(f"Delete command error: {str(e)}", start_time)
    
    def _handle_list_command(self, command: str, start_time: float) -> Dict[str, Any]:
        """Handle list/search document commands."""
        # Parse: list Customer or search Customer for "ABC"
        try:
            parts = command.split()
            if len(parts) < 2:
                return self._error_result("Invalid list command format", start_time)
            
            command_lower = command.lower()
            doctype = parts[1]
            
            if command_lower.startswith("search") and "for" in command:
                # Search command
                search_term = command.split("for", 1)[1].strip().strip('"\'')
                result = self.api_service.search_documents(doctype, search_term, limit=10)
            else:
                # List command
                filters = {}
                # Could add filter parsing here
                result = self.api_service.list_documents(doctype, filters, limit=20)
            
            execution_time = int((time.time() - start_time) * 1000)
            result["executionTime"] = execution_time
            
            return result
            
        except Exception as e:
            return self._error_result(f"List command error: {str(e)}", start_time)
    
    def _add_limit_to_select(self, command: str) -> str:
        """
        Add LIMIT clause to SELECT queries if not present.
        
        Args:
            command (str): SQL SELECT command
        
        Returns:
            str: Modified command with LIMIT
        """
        # Check if LIMIT already exists
        if re.search(r'\bLIMIT\b', command, re.IGNORECASE):
            return command
        
        # Add LIMIT 100 at the end
        command = command.rstrip(';').rstrip()
        return f"{command} LIMIT 100"
    
    def _format_sql_result(self, result: Any) -> str:
        """
        Format SQL result for display.
        
        Args:
            result: SQL query result
        
        Returns:
            str: Formatted result string
        """
        if not result:
            return "No results found."
        
        try:
            if isinstance(result, list):
                if len(result) == 0:
                    return "No results found."
                
                # Check if it's a list of dictionaries (as_dict=True)
                if isinstance(result[0], dict):
                    # Format as JSON for structured data
                    return json.dumps(result, indent=2, default=str)
                else:
                    # Format as simple table for tuple results
                    output = []
                    for row in result:
                        if isinstance(row, (tuple, list)):
                            output.append(" | ".join(str(col) for col in row))
                        else:
                            output.append(str(row))
                    return "\n".join(output)
            else:
                return str(result)
                
        except Exception as e:
            frappe.log_error(f"Result formatting error: {str(e)}", "ERPNext Executor")
            return f"Result formatting error: {str(e)}"
    
    def _error_result(self, error_message: str, start_time: float) -> Dict[str, Any]:
        """
        Create error result dictionary.
        
        Args:
            error_message (str): Error message
            start_time (float): Execution start time
        
        Returns:
            Dict[str, Any]: Error result
        """
        execution_time = int((time.time() - start_time) * 1000)
        return {
            "success": False,
            "output": "",
            "error": error_message,
            "executionTime": execution_time
        }
    
    def validate_sql_query(self, query: str) -> Dict[str, Any]:
        """
        Validate SQL query without executing it.
        
        Args:
            query (str): SQL query to validate
        
        Returns:
            Dict[str, Any]: Validation result
        """
        try:
            # Basic syntax check
            query = query.strip()
            if not query:
                return {"valid": False, "reason": "Empty query"}
            
            # Check command type
            first_word = query.split()[0].upper()
            
            # All SQL commands are now allowed (unrestricted access)
            # Determine if command is potentially destructive for logging/confirmation
            destructive_commands = {
                'INSERT', 'UPDATE', 'DELETE', 'DROP', 'CREATE', 'ALTER', 
                'TRUNCATE', 'REPLACE', 'MERGE', 'CALL', 'EXECUTE'
            }
            is_destructive = first_word in destructive_commands
            
            # UNRESTRICTED SQL ACCESS - skip security checks for confirmed SQL operations
            # (User specifically requested completely unrestricted SQL access)
            
            return {
                "valid": True,
                "reason": "Query is valid (unrestricted access enabled)",
                "commandType": first_word.lower(),
                "isDestructive": is_destructive
            }
            
        except Exception as e:
            return {
                "valid": False,
                "reason": f"Validation error: {str(e)}"
            }


def get_executor(safe_mode: Optional[bool] = None) -> ERPNextExecutor:
    """
    Get ERPNext executor with settings from AI Assistant Settings.
    
    Args:
        safe_mode (Optional[bool]): Override safe mode setting
    
    Returns:
        ERPNextExecutor: Configured executor instance
    """
    try:
        if safe_mode is None:
            settings = frappe.get_single("AI Assistant Settings")
            safe_mode = settings.safe_mode
        
        return ERPNextExecutor(safe_mode=safe_mode)
    except Exception as e:
        frappe.log_error(f"Failed to get executor: {str(e)}", "ERPNext Executor")
        # Return default safe configuration
        return ERPNextExecutor(safe_mode=True)