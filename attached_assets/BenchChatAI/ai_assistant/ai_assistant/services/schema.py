# Copyright (c) 2025, ERPNext and contributors
# For license information, please see license.txt

import json
import frappe
from typing import Dict, Any, List, Optional
from frappe import _
from frappe.utils import now_datetime, cint


class SchemaService:
    """
    Database schema scanning service for AI Assistant.
    
    Provides methods to scan and cache database schema information
    to provide better context for AI responses.
    """
    
    @staticmethod
    def scan_database(include_custom: bool = True, max_tables: int = 100) -> Dict[str, Any]:
        """
        Scan database schema and return structured information.
        
        Args:
            include_custom (bool): Include custom DocTypes
            max_tables (int): Maximum number of tables to scan
        
        Returns:
            Dict[str, Any]: Schema information
        """
        try:
            schema_info = {
                "scan_time": now_datetime().isoformat(),
                "doctypes": {},
                "tables": {},
                "summary": {
                    "total_doctypes": 0,
                    "total_tables": 0,
                    "custom_doctypes": 0
                }
            }
            
            # Scan DocTypes using Frappe meta
            schema_info["doctypes"] = SchemaService._scan_doctypes(include_custom)
            schema_info["summary"]["total_doctypes"] = len(schema_info["doctypes"])
            
            # Count custom DocTypes
            custom_count = sum(1 for dt in schema_info["doctypes"].values() 
                             if dt.get("is_custom", False))
            schema_info["summary"]["custom_doctypes"] = custom_count
            
            # Scan raw database tables
            schema_info["tables"] = SchemaService._scan_database_tables(max_tables)
            schema_info["summary"]["total_tables"] = len(schema_info["tables"])
            
            return schema_info
            
        except Exception as e:
            frappe.log_error(f"Database scan error: {str(e)}", "Schema Service")
            raise Exception(f"Failed to scan database: {str(e)}")
    
    @staticmethod
    def _scan_doctypes(include_custom: bool = True) -> Dict[str, Any]:
        """
        Scan DocTypes using Frappe's meta system.
        
        Args:
            include_custom (bool): Include custom DocTypes
        
        Returns:
            Dict[str, Any]: DocType information
        """
        doctypes_info = {}
        
        try:
            # Get all DocTypes
            filters = {}
            if not include_custom:
                filters["custom"] = 0
            
            doctype_list = frappe.get_all("DocType", 
                filters=filters,
                fields=["name", "module", "custom", "is_single", "is_tree", 
                       "is_child", "is_virtual", "description"],
                limit_page_length=200
            )
            
            for dt in doctype_list:
                try:
                    # Get meta information
                    meta = frappe.get_meta(dt["name"])
                    
                    doctype_info = {
                        "name": dt["name"],
                        "module": dt["module"],
                        "is_custom": bool(dt.get("custom")),
                        "is_single": bool(dt.get("is_single")),
                        "is_tree": bool(dt.get("is_tree")),
                        "is_child": bool(dt.get("is_child")),
                        "is_virtual": bool(dt.get("is_virtual")),
                        "description": dt.get("description", ""),
                        "fields": [],
                        "links": []
                    }
                    
                    # Get field information
                    for field in meta.fields:
                        if field.fieldtype not in ["Section Break", "Column Break", "Tab Break"]:
                            field_info = {
                                "fieldname": field.fieldname,
                                "fieldtype": field.fieldtype,
                                "label": field.label,
                                "reqd": bool(field.reqd),
                                "options": field.options if field.options else ""
                            }
                            doctype_info["fields"].append(field_info)
                    
                    # Get link fields for relationships
                    for field in meta.fields:
                        if field.fieldtype == "Link" and field.options:
                            doctype_info["links"].append({
                                "field": field.fieldname,
                                "target": field.options,
                                "label": field.label
                            })
                    
                    doctypes_info[dt["name"]] = doctype_info
                    
                except Exception as field_error:
                    frappe.log_error(f"Error scanning DocType {dt['name']}: {str(field_error)}", "Schema Service")
                    continue
            
            return doctypes_info
            
        except Exception as e:
            frappe.log_error(f"DocType scan error: {str(e)}", "Schema Service")
            return {}
    
    @staticmethod
    def _scan_database_tables(max_tables: int = 100) -> Dict[str, Any]:
        """
        Scan raw database tables using SQL.
        
        Args:
            max_tables (int): Maximum number of tables to scan
        
        Returns:
            Dict[str, Any]: Table information
        """
        tables_info = {}
        
        try:
            # Get list of tables
            tables_result = frappe.db.sql("SHOW TABLES", as_dict=False)
            table_names = [table[0] for table in tables_result[:max_tables]]
            
            for table_name in table_names:
                try:
                    # Skip certain system tables
                    if table_name.startswith('__') or table_name in ['mysql', 'information_schema', 'performance_schema']:
                        continue
                    
                    # Get table structure
                    describe_result = frappe.db.sql(f"DESCRIBE `{table_name}`", as_dict=True)
                    
                    table_info = {
                        "name": table_name,
                        "columns": [],
                        "primary_keys": [],
                        "indexes": []
                    }
                    
                    # Process columns
                    for column in describe_result:
                        column_info = {
                            "name": column.get("Field", ""),
                            "type": column.get("Type", ""),
                            "null": column.get("Null", "") == "YES",
                            "key": column.get("Key", ""),
                            "default": column.get("Default", ""),
                            "extra": column.get("Extra", "")
                        }
                        table_info["columns"].append(column_info)
                        
                        # Track primary keys
                        if column.get("Key") == "PRI":
                            table_info["primary_keys"].append(column.get("Field"))
                    
                    tables_info[table_name] = table_info
                    
                except Exception as table_error:
                    frappe.log_error(f"Error scanning table {table_name}: {str(table_error)}", "Schema Service")
                    continue
            
            return tables_info
            
        except Exception as e:
            frappe.log_error(f"Database tables scan error: {str(e)}", "Schema Service")
            return {}
    
    @staticmethod
    def get_schema_context(format_type: str = "summary") -> str:
        """
        Get cached schema context for AI assistant.
        
        Args:
            format_type (str): Format type - "summary", "detailed", or "json"
        
        Returns:
            str: Formatted schema context
        """
        try:
            # Try to get cached schema from settings
            settings = frappe.get_single("AI Assistant Settings")
            
            # Check if we have cached schema (assuming we add a field for this)
            cached_schema = getattr(settings, 'cached_schema', None)
            
            if cached_schema:
                try:
                    schema_data = json.loads(cached_schema)
                    return SchemaService._format_schema_context(schema_data, format_type)
                except json.JSONDecodeError:
                    pass
            
            # If no cached schema, generate basic context from key DocTypes
            return SchemaService._generate_basic_context(format_type)
            
        except Exception as e:
            frappe.log_error(f"Get schema context error: {str(e)}", "Schema Service")
            return "Schema context unavailable"
    
    @staticmethod
    def _generate_basic_context(format_type: str = "summary") -> str:
        """Generate basic schema context without full scan."""
        try:
            # Key ERPNext DocTypes that are commonly queried
            key_doctypes = [
                "Customer", "Supplier", "Item", "Sales Invoice", "Purchase Invoice",
                "Sales Order", "Purchase Order", "Delivery Note", "Purchase Receipt",
                "Payment Entry", "Journal Entry", "Employee", "User", "Company"
            ]
            
            context_parts = []
            
            if format_type == "summary":
                context_parts.append("ERPNext Core Entities:")
                
                for doctype in key_doctypes:
                    try:
                        if frappe.db.exists("DocType", doctype):
                            meta = frappe.get_meta(doctype)
                            key_fields = [f.fieldname for f in meta.fields[:5] 
                                        if f.fieldtype not in ["Section Break", "Column Break"]]
                            
                            context_parts.append(f"- {doctype}: {', '.join(key_fields)}")
                    except Exception:
                        continue
                        
                return "\n".join(context_parts)
            
            elif format_type == "detailed":
                context_parts.append("ERPNext Schema Context (Basic):")
                
                for doctype in key_doctypes:
                    try:
                        if frappe.db.exists("DocType", doctype):
                            meta = frappe.get_meta(doctype)
                            context_parts.append(f"\n{doctype}:")
                            context_parts.append(f"  Table: `tab{doctype}`")
                            
                            # Key fields
                            key_fields = []
                            for field in meta.fields[:10]:
                                if field.fieldtype not in ["Section Break", "Column Break", "Tab Break"]:
                                    key_fields.append(f"    {field.fieldname} ({field.fieldtype})")
                            
                            if key_fields:
                                context_parts.append("  Key Fields:")
                                context_parts.extend(key_fields)
                    except Exception:
                        continue
                        
                return "\n".join(context_parts)
            
            else:  # json format
                schema_data = {"doctypes": []}
                for doctype in key_doctypes:
                    try:
                        if frappe.db.exists("DocType", doctype):
                            meta = frappe.get_meta(doctype)
                            fields = [{"name": f.fieldname, "type": f.fieldtype, "label": f.label}
                                    for f in meta.fields[:10] 
                                    if f.fieldtype not in ["Section Break", "Column Break"]]
                            
                            schema_data["doctypes"].append({
                                "name": doctype,
                                "table": f"tab{doctype}",
                                "fields": fields
                            })
                    except Exception:
                        continue
                
                return json.dumps(schema_data, indent=2)
                
        except Exception as e:
            frappe.log_error(f"Generate basic context error: {str(e)}", "Schema Service")
            return "Basic schema context unavailable"
    
    @staticmethod
    def _format_schema_context(schema_data: Dict[str, Any], format_type: str) -> str:
        """Format schema data into context string."""
        try:
            if format_type == "json":
                return json.dumps(schema_data, indent=2)
            
            context_parts = []
            
            if format_type == "summary":
                context_parts.append(f"Database Schema (scanned: {schema_data.get('scan_time', 'unknown')}):")
                context_parts.append(f"DocTypes: {schema_data['summary']['total_doctypes']}")
                context_parts.append(f"Custom DocTypes: {schema_data['summary']['custom_doctypes']}")
                context_parts.append(f"Database Tables: {schema_data['summary']['total_tables']}")
                
                # Key DocTypes summary
                context_parts.append("\nKey DocTypes:")
                for name, info in list(schema_data['doctypes'].items())[:10]:
                    field_count = len(info.get('fields', []))
                    context_parts.append(f"- {name}: {field_count} fields")
                    
            else:  # detailed
                context_parts.append(f"Detailed Schema (scanned: {schema_data.get('scan_time', 'unknown')}):")
                
                # DocTypes details
                for name, info in list(schema_data['doctypes'].items())[:20]:
                    context_parts.append(f"\n{name}:")
                    context_parts.append(f"  Module: {info.get('module', 'unknown')}")
                    context_parts.append(f"  Custom: {info.get('is_custom', False)}")
                    
                    # Key fields
                    key_fields = info.get('fields', [])[:8]
                    if key_fields:
                        context_parts.append("  Fields:")
                        for field in key_fields:
                            req_marker = " (required)" if field.get('reqd') else ""
                            context_parts.append(f"    {field['fieldname']} ({field['fieldtype']}){req_marker}")
            
            return "\n".join(context_parts)
            
        except Exception as e:
            frappe.log_error(f"Format schema context error: {str(e)}", "Schema Service")
            return "Schema formatting error"
    
    @staticmethod
    def save_schema_to_settings(schema_data: Dict[str, Any]) -> bool:
        """
        Save schema data to AI Assistant Settings.
        
        Args:
            schema_data (Dict[str, Any]): Schema data to save
        
        Returns:
            bool: True if saved successfully
        """
        try:
            settings = frappe.get_single("AI Assistant Settings")
            
            # Convert to JSON string (with size limit)
            schema_json = json.dumps(schema_data)
            
            # Limit size to prevent database issues (e.g., 1MB limit)
            max_size = 1024 * 1024  # 1MB
            if len(schema_json) > max_size:
                # Truncate data while keeping structure
                truncated_data = {
                    "scan_time": schema_data.get("scan_time"),
                    "summary": schema_data.get("summary", {}),
                    "doctypes": dict(list(schema_data.get("doctypes", {}).items())[:50]),
                    "tables": dict(list(schema_data.get("tables", {}).items())[:50]),
                    "truncated": True
                }
                schema_json = json.dumps(truncated_data)
            
            # Save to settings - assuming we add a Long Text field called 'cached_schema'
            settings.db_set('cached_schema', schema_json, update_modified=True)
            settings.db_set('schema_last_scan', now_datetime(), update_modified=True)
            
            return True
            
        except Exception as e:
            frappe.log_error(f"Save schema error: {str(e)}", "Schema Service")
            return False


def scan_database_background():
    """
    Background job function for database scanning.
    This function is called by frappe.enqueue.
    """
    try:
        frappe.logger("schema_scan").info("Starting background database scan")
        
        # Perform full scan
        schema_data = SchemaService.scan_database(include_custom=True, max_tables=200)
        
        # Save to settings
        success = SchemaService.save_schema_to_settings(schema_data)
        
        if success:
            frappe.logger("schema_scan").info(f"Schema scan completed successfully. "
                                            f"Found {schema_data['summary']['total_doctypes']} DocTypes "
                                            f"and {schema_data['summary']['total_tables']} tables.")
        else:
            frappe.logger("schema_scan").error("Failed to save schema scan results")
            
    except Exception as e:
        frappe.log_error(f"Background schema scan error: {str(e)}", "Schema Background Scan")
        frappe.logger("schema_scan").error(f"Background scan failed: {str(e)}")


def get_schema_service() -> SchemaService:
    """
    Get SchemaService instance.
    
    Returns:
        SchemaService: Service instance
    """
    return SchemaService()