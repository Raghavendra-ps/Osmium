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


class ERPNextExecutor:
    """
    Secure command execution service for AI Assistant.
    
    Handles safe execution of database queries and limited system commands
    with comprehensive security checks and safe mode enforcement.
    """
    
    # SQL commands that are allowed
    ALLOWED_SQL_COMMANDS = {
        'SELECT', 'SHOW', 'DESCRIBE', 'DESC', 'EXPLAIN'
    }
    
    # Destructive SQL commands that require confirmation
    DESTRUCTIVE_SQL_COMMANDS = {
        'INSERT', 'UPDATE', 'DELETE', 'DROP', 'CREATE', 'ALTER', 
        'TRUNCATE', 'REPLACE', 'MERGE', 'CALL', 'EXECUTE'
    }
    
    # Allowed bench commands (very restrictive)
    ALLOWED_BENCH_COMMANDS = {
        'version', '--version', '--help', '-h', 'help'
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
    
    def execute_command(self, command: str) -> Dict[str, Any]:
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
            
            # Security checks
            security_check = self._perform_security_checks(command)
            if not security_check["safe"]:
                return self._error_result(security_check["reason"], start_time)
            
            # Determine command type and execute
            if self._is_sql_command(command):
                return self._execute_sql_command(command, start_time)
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
        return first_word in self.ALLOWED_SQL_COMMANDS or first_word in self.DESTRUCTIVE_SQL_COMMANDS
    
    def _is_bench_command(self, command: str) -> bool:
        """Check if command is a bench command."""
        return command.strip().startswith('bench ') or command.strip() in self.ALLOWED_BENCH_COMMANDS
    
    def _execute_sql_command(self, command: str, start_time: float) -> Dict[str, Any]:
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
            
            # Check if destructive command
            if first_word in self.DESTRUCTIVE_SQL_COMMANDS:
                if self.safe_mode:
                    return self._error_result(
                        f"Destructive SQL command '{first_word}' not allowed in safe mode", 
                        start_time
                    )
                else:
                    return self._error_result(
                        f"Destructive SQL command '{first_word}' requires manual confirmation", 
                        start_time
                    )
            
            # Process safe SQL commands
            if first_word == 'SELECT':
                command = self._add_limit_to_select(command)
            
            # Execute using frappe.db.sql
            if first_word in ['SHOW', 'DESCRIBE', 'DESC']:
                # These commands return simple results
                result = frappe.db.sql(command, as_dict=False)
                output = self._format_sql_result(result)
            else:
                # SELECT and EXPLAIN return structured data
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
            # Parse command
            if command.startswith('bench '):
                cmd_parts = shlex.split(command)
            else:
                cmd_parts = ['bench'] + shlex.split(command)
            
            # Validate command parts
            if not self._is_allowed_bench_command(cmd_parts[1:]):
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
        if first_arg in self.ALLOWED_BENCH_COMMANDS:
            return True
        
        # Allow specific safe commands
        safe_patterns = [
            r'^--help$',
            r'^-h$',
            r'^version$',
            r'^--version$'
        ]
        
        for pattern in safe_patterns:
            if re.match(pattern, first_arg):
                return True
        
        return False
    
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
            
            if first_word in self.DESTRUCTIVE_SQL_COMMANDS:
                return {
                    "valid": False,
                    "reason": f"Destructive command '{first_word}' not allowed",
                    "isDestructive": True
                }
            
            if first_word not in self.ALLOWED_SQL_COMMANDS:
                return {
                    "valid": False,
                    "reason": f"Command '{first_word}' not allowed"
                }
            
            # Security checks
            security_check = self._perform_security_checks(query)
            if not security_check["safe"]:
                return {
                    "valid": False,
                    "reason": security_check["reason"]
                }
            
            return {
                "valid": True,
                "reason": "Query is valid",
                "commandType": first_word.lower(),
                "isDestructive": False
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