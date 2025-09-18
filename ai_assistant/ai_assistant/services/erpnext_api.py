# Copyright (c) 2025, ERPNext and contributors
# For license information, please see license.txt

import json
import frappe
import requests
from typing import Dict, Any, List, Optional, Union
from frappe import _
from frappe.utils import cint, flt, now_datetime, get_url
from urllib.parse import urljoin


class ERPNextAPIService:
    """
    ERPNext REST API integration service for AI Assistant.
    
    Provides comprehensive document operations through ERPNext's REST API
    and direct Frappe framework methods when available.
    """
    
    def __init__(self, use_rest_api: bool = False, base_url: str = None, api_key: str = None, api_secret: str = None):
        """
        Initialize ERPNext API service.
        
        Args:
            use_rest_api (bool): Use REST API instead of direct Frappe methods
            base_url (str): Base URL for REST API calls
            api_key (str): API key for authentication (if None, loads from settings)
            api_secret (str): API secret for authentication (if None, loads from settings)
        """
        self.use_rest_api = use_rest_api
        self.base_url = base_url or get_url()
        
        # Load API credentials from settings if not provided
        if api_key is None or api_secret is None:
            try:
                settings = frappe.get_single("AI Assistant Settings")
                self.api_key = api_key or settings.get("api_key")
                self.api_secret = api_secret or settings.get("api_secret")
                
                # Get site name from settings for multi-site operations
                self.site_name = settings.get("site_name", "frontend1")
            except Exception:
                # Fallback if settings not available
                self.api_key = api_key
                self.api_secret = api_secret
                self.site_name = "frontend1"
        else:
            self.api_key = api_key
            self.api_secret = api_secret
            self.site_name = "frontend1"
        
        # Session for REST API calls with ERPNext authentication
        self.session = requests.Session()
        if self.api_key and self.api_secret:
            # ERPNext expects Authorization: token <api_key>:<api_secret>
            auth_token = f"{self.api_key}:{self.api_secret}"
            self.session.headers.update({
                'Authorization': f'token {auth_token}',
                'Content-Type': 'application/json',
                'Accept': 'application/json'
            })
            # Add site header for multi-site operations if needed
            if self.site_name:
                self.session.headers['X-Frappe-Site-Name'] = self.site_name
    
    def create_document(self, doctype: str, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Create a new document.
        
        Args:
            doctype (str): DocType name
            data (Dict[str, Any]): Document data
            
        Returns:
            Dict[str, Any]: Created document data
        """
        try:
            if self.use_rest_api:
                return self._create_document_api(doctype, data)
            else:
                return self._create_document_direct(doctype, data)
                
        except Exception as e:
            frappe.log_error(f"Create document error: {str(e)}", "ERPNext API Service")
            return {
                "success": False,
                "error": f"Failed to create {doctype}: {str(e)}"
            }
    
    def get_document(self, doctype: str, name: str, fields: List[str] = None) -> Dict[str, Any]:
        """
        Get a document by name.
        
        Args:
            doctype (str): DocType name
            name (str): Document name
            fields (List[str]): Specific fields to fetch
            
        Returns:
            Dict[str, Any]: Document data
        """
        try:
            if self.use_rest_api:
                return self._get_document_api(doctype, name, fields)
            else:
                return self._get_document_direct(doctype, name, fields)
                
        except Exception as e:
            frappe.log_error(f"Get document error: {str(e)}", "ERPNext API Service")
            return {
                "success": False,
                "error": f"Failed to get {doctype} {name}: {str(e)}"
            }
    
    def update_document(self, doctype: str, name: str, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Update an existing document.
        
        Args:
            doctype (str): DocType name
            name (str): Document name
            data (Dict[str, Any]): Update data
            
        Returns:
            Dict[str, Any]: Updated document data
        """
        try:
            if self.use_rest_api:
                return self._update_document_api(doctype, name, data)
            else:
                return self._update_document_direct(doctype, name, data)
                
        except Exception as e:
            frappe.log_error(f"Update document error: {str(e)}", "ERPNext API Service")
            return {
                "success": False,
                "error": f"Failed to update {doctype} {name}: {str(e)}"
            }
    
    def delete_document(self, doctype: str, name: str) -> Dict[str, Any]:
        """
        Delete a document.
        
        Args:
            doctype (str): DocType name
            name (str): Document name
            
        Returns:
            Dict[str, Any]: Deletion result
        """
        try:
            if self.use_rest_api:
                return self._delete_document_api(doctype, name)
            else:
                return self._delete_document_direct(doctype, name)
                
        except Exception as e:
            frappe.log_error(f"Delete document error: {str(e)}", "ERPNext API Service")
            return {
                "success": False,
                "error": f"Failed to delete {doctype} {name}: {str(e)}"
            }
    
    def list_documents(self, doctype: str, filters: Dict[str, Any] = None, 
                      fields: List[str] = None, limit: int = 20, 
                      order_by: str = None) -> Dict[str, Any]:
        """
        List documents with filtering and pagination.
        
        Args:
            doctype (str): DocType name
            filters (Dict[str, Any]): Filter conditions
            fields (List[str]): Fields to fetch
            limit (int): Number of records to fetch
            order_by (str): Order by clause
            
        Returns:
            Dict[str, Any]: List of documents
        """
        try:
            if self.use_rest_api:
                return self._list_documents_api(doctype, filters, fields, limit, order_by)
            else:
                return self._list_documents_direct(doctype, filters, fields, limit, order_by)
                
        except Exception as e:
            frappe.log_error(f"List documents error: {str(e)}", "ERPNext API Service")
            return {
                "success": False,
                "error": f"Failed to list {doctype}: {str(e)}"
            }
    
    def search_documents(self, doctype: str, search_term: str, 
                        fields: List[str] = None, limit: int = 10) -> Dict[str, Any]:
        """
        Search documents by text.
        
        Args:
            doctype (str): DocType name
            search_term (str): Search term
            fields (List[str]): Fields to search in
            limit (int): Number of results
            
        Returns:
            Dict[str, Any]: Search results
        """
        try:
            if self.use_rest_api:
                return self._search_documents_api(doctype, search_term, fields, limit)
            else:
                return self._search_documents_direct(doctype, search_term, fields, limit)
                
        except Exception as e:
            frappe.log_error(f"Search documents error: {str(e)}", "ERPNext API Service")
            return {
                "success": False,
                "error": f"Failed to search {doctype}: {str(e)}"
            }
    
    # Direct Frappe method implementations
    def _create_document_direct(self, doctype: str, data: Dict[str, Any]) -> Dict[str, Any]:
        """Create document using direct Frappe methods."""
        # Check permissions
        if not frappe.has_permission(doctype, "create"):
            return {
                "success": False,
                "error": f"No permission to create {doctype}"
            }
        
        # Create document
        doc = frappe.get_doc(dict(data, doctype=doctype))
        doc.insert()
        
        return {
            "success": True,
            "data": doc.as_dict(),
            "name": doc.name,
            "message": f"{doctype} created successfully"
        }
    
    def _get_document_direct(self, doctype: str, name: str, fields: List[str] = None) -> Dict[str, Any]:
        """Get document using direct Frappe methods."""
        # Check if document exists
        if not frappe.db.exists(doctype, name):
            return {
                "success": False,
                "error": f"{doctype} {name} not found"
            }
        
        # Get document first for proper permission check
        doc = frappe.get_doc(doctype, name)
        
        # Check permissions with actual document
        if not frappe.has_permission(doctype, "read", doc=doc):
            return {
                "success": False,
                "error": f"No permission to read {doctype} {name}"
            }
        
        # Return document data
        if fields:
            doc_data = {field: doc.get(field) for field in fields if hasattr(doc, field)}
        else:
            doc_data = doc.as_dict()
        
        return {
            "success": True,
            "data": doc_data
        }
    
    def _update_document_direct(self, doctype: str, name: str, data: Dict[str, Any]) -> Dict[str, Any]:
        """Update document using direct Frappe methods."""
        # Check if document exists
        if not frappe.db.exists(doctype, name):
            return {
                "success": False,
                "error": f"{doctype} {name} not found"
            }
        
        # Get document first for proper permission check
        doc = frappe.get_doc(doctype, name)
        
        # Check permissions with actual document
        if not frappe.has_permission(doctype, "write", doc=doc):
            return {
                "success": False,
                "error": f"No permission to update {doctype} {name}"
            }
        doc.update(data)
        doc.save()
        
        return {
            "success": True,
            "data": doc.as_dict(),
            "message": f"{doctype} {name} updated successfully"
        }
    
    def _delete_document_direct(self, doctype: str, name: str) -> Dict[str, Any]:
        """Delete document using direct Frappe methods."""
        # Check if document exists
        if not frappe.db.exists(doctype, name):
            return {
                "success": False,
                "error": f"{doctype} {name} not found"
            }
        
        # Get document for proper permission check
        doc = frappe.get_doc(doctype, name)
        
        # Check permissions with actual document
        if not frappe.has_permission(doctype, "delete", doc=doc):
            return {
                "success": False,
                "error": f"No permission to delete {doctype} {name}"
            }
        
        # Delete document
        frappe.delete_doc(doctype, name)
        
        return {
            "success": True,
            "message": f"{doctype} {name} deleted successfully"
        }
    
    def _list_documents_direct(self, doctype: str, filters: Dict[str, Any] = None, 
                              fields: List[str] = None, limit: int = 20, 
                              order_by: str = None) -> Dict[str, Any]:
        """List documents using direct Frappe methods."""
        # Check permissions
        if not frappe.has_permission(doctype, "read"):
            return {
                "success": False,
                "error": f"No permission to read {doctype}"
            }
        
        # Build query parameters
        query_params = {
            "doctype": doctype,
            "limit_page_length": limit
        }
        
        if filters:
            query_params["filters"] = filters
        if fields:
            query_params["fields"] = fields
        if order_by:
            query_params["order_by"] = order_by
        
        # Get documents
        documents = frappe.get_all(**query_params)
        
        return {
            "success": True,
            "data": documents,
            "count": len(documents)
        }
    
    def _search_documents_direct(self, doctype: str, search_term: str, 
                                fields: List[str] = None, limit: int = 10) -> Dict[str, Any]:
        """Search documents using direct Frappe methods."""
        # Check permissions
        if not frappe.has_permission(doctype, "read"):
            return {
                "success": False,
                "error": f"No permission to read {doctype}"
            }
        
        # Perform search
        results = frappe.db.sql("""
            SELECT name, title, {fields}
            FROM `tab{doctype}`
            WHERE title LIKE %s OR name LIKE %s
            ORDER BY modified DESC
            LIMIT %s
        """.format(
            fields=", ".join(fields) if fields else "*",
            doctype=doctype
        ), (f"%{search_term}%", f"%{search_term}%", limit), as_dict=True)
        
        return {
            "success": True,
            "data": results,
            "count": len(results)
        }
    
    # REST API method implementations (for external ERPNext instances)
    def _create_document_api(self, doctype: str, data: Dict[str, Any]) -> Dict[str, Any]:
        """Create document using REST API."""
        url = urljoin(self.base_url, f"/api/resource/{doctype}")
        response = self.session.post(url, json=data)
        
        if response.status_code == 200:
            return {
                "success": True,
                "data": response.json().get("data"),
                "message": f"{doctype} created successfully"
            }
        else:
            return {
                "success": False,
                "error": f"API Error: {response.status_code} - {response.text}"
            }
    
    def _get_document_api(self, doctype: str, name: str, fields: List[str] = None) -> Dict[str, Any]:
        """Get document using REST API."""
        url = urljoin(self.base_url, f"/api/resource/{doctype}/{name}")
        params = {}
        if fields:
            params["fields"] = json.dumps(fields)
        
        response = self.session.get(url, params=params)
        
        if response.status_code == 200:
            return {
                "success": True,
                "data": response.json().get("data")
            }
        else:
            return {
                "success": False,
                "error": f"API Error: {response.status_code} - {response.text}"
            }
    
    def _update_document_api(self, doctype: str, name: str, data: Dict[str, Any]) -> Dict[str, Any]:
        """Update document using REST API."""
        url = urljoin(self.base_url, f"/api/resource/{doctype}/{name}")
        response = self.session.put(url, json=data)
        
        if response.status_code == 200:
            return {
                "success": True,
                "data": response.json().get("data"),
                "message": f"{doctype} {name} updated successfully"
            }
        else:
            return {
                "success": False,
                "error": f"API Error: {response.status_code} - {response.text}"
            }
    
    def _delete_document_api(self, doctype: str, name: str) -> Dict[str, Any]:
        """Delete document using REST API."""
        url = urljoin(self.base_url, f"/api/resource/{doctype}/{name}")
        response = self.session.delete(url)
        
        if response.status_code == 202:
            return {
                "success": True,
                "message": f"{doctype} {name} deleted successfully"
            }
        else:
            return {
                "success": False,
                "error": f"API Error: {response.status_code} - {response.text}"
            }
    
    def _list_documents_api(self, doctype: str, filters: Dict[str, Any] = None, 
                           fields: List[str] = None, limit: int = 20, 
                           order_by: str = None) -> Dict[str, Any]:
        """List documents using REST API."""
        url = urljoin(self.base_url, f"/api/resource/{doctype}")
        params = {"limit_page_length": limit}
        
        if filters:
            params["filters"] = json.dumps(filters)
        if fields:
            params["fields"] = json.dumps(fields)
        if order_by:
            params["order_by"] = order_by
        
        response = self.session.get(url, params=params)
        
        if response.status_code == 200:
            return {
                "success": True,
                "data": response.json().get("data"),
                "count": len(response.json().get("data", []))
            }
        else:
            return {
                "success": False,
                "error": f"API Error: {response.status_code} - {response.text}"
            }
    
    def _search_documents_api(self, doctype: str, search_term: str, 
                             fields: List[str] = None, limit: int = 10) -> Dict[str, Any]:
        """Search documents using REST API."""
        url = urljoin(self.base_url, f"/api/resource/{doctype}")
        params = {
            "limit_page_length": limit,
            "filters": json.dumps([["name", "like", f"%{search_term}%"]])
        }
        
        if fields:
            params["fields"] = json.dumps(fields)
        
        response = self.session.get(url, params=params)
        
        if response.status_code == 200:
            return {
                "success": True,
                "data": response.json().get("data"),
                "count": len(response.json().get("data", []))
            }
        else:
            return {
                "success": False,
                "error": f"API Error: {response.status_code} - {response.text}"
            }


def get_erpnext_api_service() -> ERPNextAPIService:
    """
    Get ERPNext API service instance.
    
    Returns:
        ERPNextAPIService: Service instance
    """
    return ERPNextAPIService()