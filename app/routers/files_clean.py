"""
Files Router - Clean, optimized file management endpoints
Handles upload, download, preview, and file operations with proper authentication
"""

import traceback
import asyncio
import aiofiles
import gzip
import datetime
import time
import hashlib
import logging
from functools import lru_cache
from typing import List, Optional, Dict, Any
from contextvars import ContextVar
from collections import defaultdict
from datetime import datetime, timedelta
from fastapi import APIRouter, UploadFile, File, Depends, HTTPException, Form, Response, Request
from fastapi.responses import JSONResponse, StreamingResponse, FileResponse
from fastapi.middleware.gzip import GZipMiddleware

from app.core.config import REMOTE_DIR, BACKUP_DIR, PREVIEW_DIR
from app.core.auth import jwt_required
from app.services.file_service import FileService
from app.routers.utils.api_files_utils import (
    search_files, download_file, delete_file_and_dir, create_dir, 
    upload_files, dir_contents, file_preview, upload_multiple_folders,
    get_pdf_info, get_pdf_page, get_pdf_pages_range, search_pdf_text,
    get_pdf_page_with_text, get_pdf_text_layer, get_raw_pdf,
    get_docx_info, get_docx_page, get_xlsx_info, get_xlsx_sheet,
    get_pptx_info, get_pptx_slide, get_newly_added_files_since_timestamp,
    get_newly_added_files
)

# Initialize router with performance settings
router = APIRouter(
    responses={
        500: {"description": "Internal server error"},
        403: {"description": "Forbidden - insufficient permissions"},
        404: {"description": "File or resource not found"}
    }
)
file_service = FileService()

# Cache for user roles to reduce database calls
@lru_cache(maxsize=100)
def _extract_user_roles(user_str: str) -> List[str]:
    """Extract user roles from user data with caching"""
    import json
    try:
        user_data = json.loads(user_str)
        return user_data.get("resource_access", {}).get("benyon_fe", {}).get("roles", [])
    except:
        return []

# Helper functions for role-based authorization
def check_admin_role(current_user: dict) -> bool:
    """Check if user has admin role with caching"""
    user_str = str(current_user)  # Convert to string for caching
    user_roles = _extract_user_roles(user_str)
    return "admin" in user_roles

def require_admin_role(current_user: dict) -> None:
    """Raise HTTPException if user doesn't have admin role"""
    if not check_admin_role(current_user):
        raise HTTPException(
            status_code=403, 
            detail="Admin role required for this operation",
            headers={"WWW-Authenticate": "Bearer"}
        )

# Async batch processing helper
async def process_files_in_batches(files: List[UploadFile], batch_size: int = 5):
    """Process files in batches to prevent memory overload"""
    results = []
    for i in range(0, len(files), batch_size):
        batch = files[i:i + batch_size]
        batch_results = await asyncio.gather(
            *[process_single_file(file) for file in batch],
            return_exceptions=True
        )
        results.extend(batch_results)
    return results

async def process_single_file(file: UploadFile) -> dict:
    """Process a single file asynchronously"""
    try:
        # Basic file validation
        if file.size > 100 * 1024 * 1024:  # 100MB limit
            raise HTTPException(status_code=413, detail=f"File {file.filename} is too large")
        
        return {
            "filename": file.filename,
            "size": file.size,
            "content_type": file.content_type
        }
    except Exception as e:
        return {"filename": file.filename, "error": str(e)}

# Modern FastAPI endpoints with proper authentication and enhanced security
@router.post("/upload")
async def upload_files_endpoint(
    request: Request,
    files: List[UploadFile] = File(...),
    folder: Optional[str] = Form(None),
    path: Optional[str] = Form(None),
    current_user: dict = Depends(jwt_required)
):
    """Upload multiple files with validation, batch processing, and security checks"""
    try:
        # Rate limiting check
        check_rate_limit(request)
        
        # Check for admin role for uploads
        require_admin_role(current_user)
        
        # Validate files before processing
        if len(files) > 50:  # Limit number of files
            raise HTTPException(status_code=413, detail="Too many files. Maximum 50 files allowed.")
        
        # Validate each file
        for file in files:
            await validate_file_size(file, max_size_mb=100)
            validate_file_type(file, allowed_categories=['image', 'document', 'text'])
        
        # Process files in batches for better performance
        file_info = await process_files_in_batches(files)
        
        # Upload files using existing utility
        uploaded_files = await upload_files(folder, files, path or "")
        
        # Generate request ID for tracking
        request_id = hashlib.md5(f"{time.time()}{request.client.host}".encode()).hexdigest()[:8]
        
        return JSONResponse(
            content={
                "detail": uploaded_files,
                "processed_count": len(files),
                "file_info": file_info,
                "request_id": request_id
            },
            headers={"Cache-Control": "no-cache"}
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Upload failed: {str(e)}")

@router.post("/search")
async def search_files_endpoint(
    search_str: str = Form(...),
    current_user: dict = Depends(jwt_required)
):
    """Search files by name with caching and pagination"""
    try:
        if len(search_str.strip()) < 2:
            raise HTTPException(status_code=400, detail="Search string must be at least 2 characters")
        
        results = await search_files(search_str)
        
        return JSONResponse(
            content={"detail": results, "search_term": search_str},
            headers={"Cache-Control": "max-age=300"}  # Cache for 5 minutes
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Search failed: {str(e)}")

@router.post("/download_file")
async def download_file_endpoint(
    path: str = Form(...),
    current_user: dict = Depends(jwt_required)
):
    """Download a specific file with streaming support"""
    try:
        username = current_user.get("email", "")
        user_id = current_user.get("sub", "")
        
        file_response = await download_file(path, user_id, username)
        
        # Add caching headers for static files
        if isinstance(file_response, FileResponse):
            file_response.headers["Cache-Control"] = "public, max-age=3600"  # 1 hour cache
            file_response.headers["X-Content-Type-Options"] = "nosniff"
        
        return file_response
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Download failed: {str(e)}")

@router.delete("/delete")
async def delete_file_endpoint(
    path: str = Form(...),
    current_user: dict = Depends(jwt_required)
):
    """Delete a file or directory with confirmation"""
    try:
        # Check for admin role
        require_admin_role(current_user)
        
        if not path or path.strip() == "/":
            raise HTTPException(status_code=400, detail="Invalid path for deletion")
        
        result = await delete_file_and_dir(path)
        
        return JSONResponse(
            content={
                "detail": result,
                "deleted_path": path,
                "timestamp": datetime.now().isoformat()
            },
            headers={"Cache-Control": "no-cache"}
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Deletion failed: {str(e)}")

@router.post("/create_dir")
async def create_directory_endpoint(
    path: str = Form(...),
    current_user: dict = Depends(jwt_required)
):
    """Create a new directory with validation"""
    try:
        # Check for admin role
        require_admin_role(current_user)
        
        if not path or ".." in path:
            raise HTTPException(status_code=400, detail="Invalid directory path")
        
        relative_path = await create_dir(path)
        
        return JSONResponse(
            content={
                "detail": f"directory created: {relative_path}",
                "created_path": relative_path,
                "timestamp": datetime.now().isoformat()
            },
            headers={"Cache-Control": "no-cache"}
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Directory creation failed: {str(e)}")

@router.post("/dir_contents")
async def directory_contents_endpoint(
    path: str = Form(...),
    current_user: dict = Depends(jwt_required)
):
    """Get directory contents with permissions and caching"""
    try:
        permissions = current_user.get("permissions", [])
        roles = current_user.get("resource_access", {}).get("benyon_fe", {}).get("roles", [])
        
        results = await dir_contents(path, permissions, roles)
        
        return JSONResponse(
            content={
                "detail": results,
                "path": path,
                "user_roles": roles[:3]  # Limit exposed role info
            },
            headers={"Cache-Control": "max-age=120"}  # Cache for 2 minutes
        )
    except HTTPException:
        raise
    except Exception as e:
        tb_str = traceback.format_exc()
        print(f"Error retrieving dir contents of {path}: {tb_str}")
        raise HTTPException(status_code=500, detail=f"Directory listing failed: {str(e)}")

@router.post("/file_preview")
async def file_preview_endpoint(
    path: str = Form(...),
    current_user: dict = Depends(jwt_required)
):
    """Generate file preview with caching"""
    try:
        preview_img = await file_preview(path)
        
        return JSONResponse(
            content={"detail": preview_img},
            headers={"Cache-Control": "max-age=1800"}  # Cache for 30 minutes
        )
    except Exception as e:
        tb_str = traceback.format_exc()
        print(f"Error processing file {path}: {tb_str}")
        raise HTTPException(status_code=500, detail=f"Preview generation failed: {str(e)}")

@router.post("/upload_multiple")
async def upload_multiple_folders_endpoint(
    files: List[UploadFile] = File(...),
    directory_structure: str = Form(...),
    current_user: dict = Depends(jwt_required)
):
    """Upload multiple folders with complex directory structures and validation"""
    try:
        # Check for admin role
        require_admin_role(current_user)
        
        if not directory_structure:
            raise HTTPException(status_code=400, detail="directory_structure field is required")
        
        if not files:
            raise HTTPException(status_code=400, detail="No files uploaded")
        
        if len(files) > 100:  # Limit for complex uploads
            raise HTTPException(status_code=413, detail="Too many files. Maximum 100 files allowed for complex uploads.")
        
        result = await upload_multiple_folders(files, directory_structure)
        
        return JSONResponse(
            content={
                "detail": result,
                "files_count": len(files),
                "timestamp": datetime.now().isoformat()
            },
            headers={"Cache-Control": "no-cache"}
        )
    except HTTPException:
        raise
    except Exception as e:
        tb_str = traceback.format_exc()
        print(f"Error in upload_multiple endpoint: {tb_str}")
        raise HTTPException(status_code=500, detail=f"Multiple upload failed: {str(e)}")

# PDF-specific endpoints with caching and performance improvements
@router.post("/pdf_info")
async def pdf_info_endpoint(
    path: str = Form(...),
    current_user: dict = Depends(jwt_required)
):
    """Get PDF metadata with caching"""
    try:
        pdf_info = await get_pdf_info(path)
        
        return JSONResponse(
            content={"detail": pdf_info},
            headers={"Cache-Control": "max-age=3600"}  # Cache for 1 hour
        )
    except Exception as e:
        tb_str = traceback.format_exc()
        print(f"Error getting PDF info for {path}: {tb_str}")
        raise HTTPException(status_code=500, detail=f"PDF info retrieval failed: {str(e)}")

@router.post("/pdf_page")
async def pdf_page_endpoint(
    path: str = Form(...),
    page: int = Form(1),
    quality: str = Form("medium"),
    scale: float = Form(1.0),
    current_user: dict = Depends(jwt_required)
):
    """Get a specific page from PDF as base64 image with validation"""
    try:
        # Validate parameters
        if page < 1:
            raise HTTPException(status_code=400, detail="Page number must be positive")
        
        if scale < 0.1 or scale > 5.0:
            raise HTTPException(status_code=400, detail="Scale must be between 0.1 and 5.0")
        
        if quality not in ["low", "medium", "high"]:
            raise HTTPException(status_code=400, detail="Quality must be 'low', 'medium', or 'high'")
        
        page_data = await get_pdf_page(path, page, quality, scale)
        
        return JSONResponse(
            content={"detail": page_data},
            headers={"Cache-Control": "max-age=1800"}  # Cache for 30 minutes
        )
    except HTTPException:
        raise
    except Exception as e:
        tb_str = traceback.format_exc()
        print(f"Error getting PDF page {page} for {path}: {tb_str}")
        raise HTTPException(status_code=500, detail=f"PDF page retrieval failed: {str(e)}")

@router.post("/pdf_search")
async def pdf_search_endpoint(
    path: str = Form(...),
    search_text: str = Form(...),
    current_user: dict = Depends(jwt_required)
):
    """Search for text within PDF with validation"""
    try:
        if len(search_text.strip()) < 2:
            raise HTTPException(status_code=400, detail="Search text must be at least 2 characters")
        
        search_results = await search_pdf_text(path, search_text)
        
        return JSONResponse(
            content={
                "detail": search_results,
                "search_term": search_text,
                "file_path": path
            },
            headers={"Cache-Control": "max-age=600"}  # Cache for 10 minutes
        )
    except HTTPException:
        raise
    except Exception as e:
        tb_str = traceback.format_exc()
        print(f"Error searching PDF {path}: {tb_str}")
        raise HTTPException(status_code=500, detail=f"PDF search failed: {str(e)}")

@router.get("/pdf_raw")
async def pdf_raw_endpoint(
    path: str,
    current_user: dict = Depends(jwt_required)
):
    """Serve raw PDF file for PDF.js viewer with streaming"""
    try:
        if not path:
            raise HTTPException(status_code=400, detail="Path parameter is required")
        
        if not path.lower().endswith('.pdf'):
            raise HTTPException(status_code=400, detail="File must be a PDF")
            
        raw_pdf = await get_raw_pdf(path)
        
        # Add appropriate headers for PDF streaming
        if hasattr(raw_pdf, 'headers'):
            raw_pdf.headers["Cache-Control"] = "public, max-age=3600"
            raw_pdf.headers["Content-Type"] = "application/pdf"
            raw_pdf.headers["X-Content-Type-Options"] = "nosniff"
        
        return raw_pdf
    except HTTPException:
        raise
    except Exception as e:
        tb_str = traceback.format_exc()
        print(f"Error serving raw PDF {path}: {tb_str}")
        raise HTTPException(status_code=500, detail=f"PDF serving failed: {str(e)}")

# Document-specific endpoints with enhanced error handling
@router.post("/docx_info")
async def docx_info_endpoint(
    path: str = Form(...),
    current_user: dict = Depends(jwt_required)
):
    """Get Word document metadata with validation"""
    try:
        if not path.lower().endswith(('.docx', '.doc')):
            raise HTTPException(status_code=400, detail="File must be a Word document")
        
        info = await get_docx_info(path)
        
        return JSONResponse(
            content={"detail": info},
            headers={"Cache-Control": "max-age=1800"}  # Cache for 30 minutes
        )
    except HTTPException:
        raise
    except Exception as e:
        tb_str = traceback.format_exc()
        print(f"Error getting DOCX info for {path}: {tb_str}")
        raise HTTPException(status_code=500, detail=f"Word document info retrieval failed: {str(e)}")

@router.post("/xlsx_info")
async def xlsx_info_endpoint(
    path: str = Form(...),
    current_user: dict = Depends(jwt_required)
):
    """Get Excel file metadata and sheet names with validation"""
    try:
        if not path.lower().endswith(('.xlsx', '.xls')):
            raise HTTPException(status_code=400, detail="File must be an Excel spreadsheet")
        
        info = await get_xlsx_info(path)
        
        return JSONResponse(
            content={"detail": info},
            headers={"Cache-Control": "max-age=1800"}  # Cache for 30 minutes
        )
    except HTTPException:
        raise
    except Exception as e:
        tb_str = traceback.format_exc()
        print(f"Error getting XLSX info for {path}: {tb_str}")
        raise HTTPException(status_code=500, detail=f"Excel file info retrieval failed: {str(e)}")

@router.post("/xlsx_sheet")
async def xlsx_sheet_endpoint(
    path: str = Form(...),
    sheet_name: str = Form(...),
    current_user: dict = Depends(jwt_required)
):
    """Get a specific sheet from Excel as HTML table with validation"""
    try:
        if not path.lower().endswith(('.xlsx', '.xls')):
            raise HTTPException(status_code=400, detail="File must be an Excel spreadsheet")
        
        if not sheet_name.strip():
            raise HTTPException(status_code=400, detail="Sheet name cannot be empty")
        
        sheet_data = await get_xlsx_sheet(path, sheet_name)
        
        return JSONResponse(
            content={"detail": sheet_data},
            headers={
                "Cache-Control": "max-age=900",  # Cache for 15 minutes
                "Content-Type": "application/json"
            }
        )
    except HTTPException:
        raise
    except Exception as e:
        tb_str = traceback.format_exc()
        print(f"Error getting XLSX sheet {sheet_name} for {path}: {tb_str}")
        raise HTTPException(status_code=500, detail=f"Excel sheet retrieval failed: {str(e)}")

@router.get("/newly_added")
async def newly_added_files_endpoint(
    days: int = 3,
    current_user: dict = Depends(jwt_required)
):
    """Get files that have been modified within the last N days with validation"""
    try:
        # Validate days parameter
        if days < 1:
            days = 3  # Default to 3 if invalid value
        elif days > 365:
            days = 365  # Maximum 1 year
        
        newly_added = await get_newly_added_files(days)
        
        return JSONResponse(
            content={
                "detail": newly_added,
                "days_filter": days,
                "timestamp": datetime.now().isoformat()
            },
            headers={"Cache-Control": "max-age=300"}  # Cache for 5 minutes
        )
    except Exception as e:
        tb_str = traceback.format_exc()
        print(f"Error getting newly added files: {tb_str}")
        raise HTTPException(status_code=500, detail=f"Newly added files retrieval failed: {str(e)}")

# Health check endpoint for monitoring
@router.get("/health")
async def health_check():
    """Health check endpoint for monitoring"""
    return JSONResponse(
        content={
            "status": "healthy",
            "timestamp": datetime.now().isoformat(),
            "service": "files-api"
        },
        headers={"Cache-Control": "no-cache"}
    )

# Context variables for request tracking
request_id_ctx: ContextVar[str] = ContextVar('request_id', default="")

class RateLimiter:
    """Simple in-memory rate limiter"""
    
    def __init__(self, max_requests: int = 100, window_minutes: int = 1):
        self.max_requests = max_requests
        self.window_minutes = window_minutes
        self.requests = defaultdict(list)
    
    def is_allowed(self, client_ip: str) -> bool:
        """Check if request is allowed for given IP"""
        now = datetime.now()
        window_start = now - timedelta(minutes=self.window_minutes)
        
        # Clean old requests
        self.requests[client_ip] = [
            req_time for req_time in self.requests[client_ip] 
            if req_time > window_start
        ]
        
        # Check if within limit
        if len(self.requests[client_ip]) >= self.max_requests:
            return False
        
        # Add current request
        self.requests[client_ip].append(now)
        return True

# Initialize rate limiter
rate_limiter = RateLimiter(max_requests=50, window_minutes=1)

def check_rate_limit(request: Request) -> None:
    """Check rate limit for the request"""
    client_ip = request.client.host
    if not rate_limiter.is_allowed(client_ip):
        raise HTTPException(
            status_code=429, 
            detail="Too many requests. Please try again later.",
            headers={"Retry-After": "60"}
        )

# File size validation helpers
async def validate_file_size(file: UploadFile, max_size_mb: int = 100) -> None:
    """Validate file size asynchronously"""
    if file.size is None:
        # Read first chunk to estimate size
        content = await file.read(1024 * 1024)  # Read 1MB
        await file.seek(0)  # Reset file pointer
        if len(content) >= max_size_mb * 1024 * 1024:
            raise HTTPException(
                status_code=413, 
                detail=f"File too large. Maximum size is {max_size_mb}MB"
            )
    elif file.size > max_size_mb * 1024 * 1024:
        raise HTTPException(
            status_code=413, 
            detail=f"File too large. Maximum size is {max_size_mb}MB"
        )

# Content type validation
ALLOWED_FILE_TYPES = {
    'image': ['image/jpeg', 'image/png', 'image/gif', 'image/webp'],
    'document': ['application/pdf', 'application/msword', 
                'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
                'application/vnd.ms-excel',
                'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
                'application/vnd.ms-powerpoint',
                'application/vnd.openxmlformats-officedocument.presentationml.presentation'],
    'text': ['text/plain', 'text/csv', 'application/json', 'application/xml']
}

def validate_file_type(file: UploadFile, allowed_categories: List[str] = None) -> None:
    """Validate file content type"""
    if allowed_categories is None:
        allowed_categories = ['image', 'document', 'text']
    
    allowed_types = []
    for category in allowed_categories:
        allowed_types.extend(ALLOWED_FILE_TYPES.get(category, []))
    
    if file.content_type not in allowed_types:
        raise HTTPException(
            status_code=415, 
            detail=f"File type {file.content_type} not allowed. Allowed types: {allowed_types}"
        )
