"""
Files Router - Clean, optimized file management endpoints
Handles upload, download, preview, and file operations with proper authentication
"""

import traceback
from fastapi import APIRouter, UploadFile, File, Depends, HTTPException, Request, Form
from fastapi.responses import FileResponse, JSONResponse
from typing import List, Optional
import os
import shutil
from datetime import datetime
from pathlib import Path

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

router = APIRouter()
file_service = FileService()

# Modern FastAPI endpoints with proper authentication
@router.post("/upload")
async def upload_files_endpoint(
    files: List[UploadFile] = File(...),
    folder: Optional[str] = Form(None),
    path: Optional[str] = Form(None),
    current_user: dict = Depends(jwt_required)
):
    """Upload multiple files with validation"""
    try:
        # Check for admin role for uploads
        user_roles = current_user.get("resource_access", {}).get("benyon_fe", {}).get("roles", [])
        if "admin" not in user_roles:
            raise HTTPException(status_code=403, detail="Admin role required for file uploads")
        
        uploaded_files = await upload_files(folder, files, path or "")
        return JSONResponse(content={"detail": uploaded_files})
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/search")
async def search_files_endpoint(
    search_str: str = Form(...),
    current_user: dict = Depends(jwt_required)
):
    """Search files by name"""
    try:
        results = await search_files(search_str)
        return JSONResponse(content={"detail": results})
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/download_file")
async def download_file_endpoint(
    path: str = Form(...),
    current_user: dict = Depends(jwt_required)
):
    """Download a specific file"""
    try:
        username = current_user.get("email", "")
        user_id = current_user.get("sub", "")
        
        file_response = await download_file(path, user_id, username)
        return file_response
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.delete("/delete")
async def delete_file_endpoint(
    path: str = Form(...),
    current_user: dict = Depends(jwt_required)
):
    """Delete a file or directory"""
    try:
        # Check for admin role
        user_roles = current_user.get("resource_access", {}).get("benyon_fe", {}).get("roles", [])
        if "admin" not in user_roles:
            raise HTTPException(status_code=403, detail="Admin role required for deletion")
        
        result = await delete_file_and_dir(path)
        return JSONResponse(content={"detail": result})
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/create_dir")
async def create_directory_endpoint(
    path: str = Form(...),
    current_user: dict = Depends(jwt_required)
):
    """Create a new directory"""
    try:
        # Check for admin role
        user_roles = current_user.get("resource_access", {}).get("benyon_fe", {}).get("roles", [])
        if "admin" not in user_roles:
            raise HTTPException(status_code=403, detail="Admin role required for directory creation")
        
        relative_path = await create_dir(path)
        return JSONResponse(content={"detail": f"directory created: {relative_path}"})
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/dir_contents")
async def directory_contents_endpoint(
    path: str = Form(...),
    current_user: dict = Depends(jwt_required)
):
    """Get directory contents with permissions"""
    try:
        permissions = current_user.get("permissions", [])
        roles = current_user.get("resource_access", {}).get("benyon_fe", {}).get("roles", [])
        
        results = await dir_contents(path, permissions, roles)
        return JSONResponse(content={"detail": results})
    except HTTPException as he:
        raise he
    except Exception as e:
        tb_str = traceback.format_exc()
        print(f"Error retrieving dir contents of {path}: {tb_str}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/file_preview")
async def file_preview_endpoint(
    path: str = Form(...),
    current_user: dict = Depends(jwt_required)
):
    """Generate file preview"""
    try:
        preview_img = await file_preview(path)
        return JSONResponse(content={"detail": preview_img})
    except Exception as e:
        tb_str = traceback.format_exc()
        print(f"Error processing file {path}: {tb_str}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/upload_multiple")
async def upload_multiple_folders_endpoint(
    files: List[UploadFile] = File(...),
    directory_structure: str = Form(...),
    current_user: dict = Depends(jwt_required)
):
    """Upload multiple folders with complex directory structures"""
    try:
        # Check for admin role
        user_roles = current_user.get("resource_access", {}).get("benyon_fe", {}).get("roles", [])
        if "admin" not in user_roles:
            raise HTTPException(status_code=403, detail="Admin role required for bulk uploads")
        
        if not directory_structure:
            raise HTTPException(status_code=400, detail="directory_structure field is required")
        
        if not files:
            raise HTTPException(status_code=400, detail="No files uploaded")
        
        result = await upload_multiple_folders(files, directory_structure)
        return JSONResponse(content={"detail": result})
    except HTTPException as he:
        raise he
    except Exception as e:
        tb_str = traceback.format_exc()
        print(f"Error in upload_multiple endpoint: {tb_str}")
        raise HTTPException(status_code=500, detail=str(e))

# PDF-specific endpoints
@router.post("/pdf_info")
async def pdf_info_endpoint(
    path: str = Form(...),
    current_user: dict = Depends(jwt_required)
):
    """Get PDF metadata"""
    try:
        pdf_info = await get_pdf_info(path)
        return JSONResponse(content={"detail": pdf_info})
    except Exception as e:
        tb_str = traceback.format_exc()
        print(f"Error getting PDF info for {path}: {tb_str}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/pdf_page")
async def pdf_page_endpoint(
    path: str = Form(...),
    page: int = Form(1),
    quality: str = Form("medium"),
    scale: float = Form(1.0),
    current_user: dict = Depends(jwt_required)
):
    """Get a specific page from PDF as base64 image"""
    try:
        page_data = await get_pdf_page(path, page, quality, scale)
        return JSONResponse(content={"detail": page_data})
    except Exception as e:
        tb_str = traceback.format_exc()
        print(f"Error getting PDF page {page} for {path}: {tb_str}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/pdf_search")
async def pdf_search_endpoint(
    path: str = Form(...),
    search_text: str = Form(...),
    current_user: dict = Depends(jwt_required)
):
    """Search for text within PDF"""
    try:
        search_results = await search_pdf_text(path, search_text)
        return JSONResponse(content={"detail": search_results})
    except Exception as e:
        tb_str = traceback.format_exc()
        print(f"Error searching PDF {path}: {tb_str}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/pdf_raw")
async def pdf_raw_endpoint(
    path: str,
    current_user: dict = Depends(jwt_required)
):
    """Serve raw PDF file for PDF.js viewer"""
    try:
        if not path:
            raise HTTPException(status_code=400, detail="Path parameter is required")
            
        raw_pdf = await get_raw_pdf(path)
        return raw_pdf
    except Exception as e:
        tb_str = traceback.format_exc()
        print(f"Error serving raw PDF {path}: {tb_str}")
        raise HTTPException(status_code=500, detail=str(e))

# Document-specific endpoints
@router.post("/docx_info")
async def docx_info_endpoint(
    path: str = Form(...),
    current_user: dict = Depends(jwt_required)
):
    """Get Word document metadata"""
    try:
        info = await get_docx_info(path)
        return JSONResponse(content={"detail": info})
    except Exception as e:
        tb_str = traceback.format_exc()
        print(f"Error getting DOCX info for {path}: {tb_str}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/xlsx_info")
async def xlsx_info_endpoint(
    path: str = Form(...),
    current_user: dict = Depends(jwt_required)
):
    """Get Excel file metadata and sheet names"""
    try:
        info = await get_xlsx_info(path)
        return JSONResponse(content={"detail": info})
    except Exception as e:
        tb_str = traceback.format_exc()
        print(f"Error getting XLSX info for {path}: {tb_str}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/xlsx_sheet")
async def xlsx_sheet_endpoint(
    path: str = Form(...),
    sheet_name: str = Form(...),
    current_user: dict = Depends(jwt_required)
):
    """Get a specific sheet from Excel as HTML table"""
    try:
        sheet_data = await get_xlsx_sheet(path, sheet_name)
        return JSONResponse(content={"detail": sheet_data})
    except Exception as e:
        tb_str = traceback.format_exc()
        print(f"Error getting XLSX sheet {sheet_name} for {path}: {tb_str}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/newly_added")
async def newly_added_files_endpoint(
    days: int = 3,
    current_user: dict = Depends(jwt_required)
):
    """Get files that have been modified within the last N days"""
    try:
        if days < 1:
            days = 3  # Default to 3 if invalid value
        
        newly_added = await get_newly_added_files(days)
        return JSONResponse(content={"detail": newly_added})
    except Exception as e:
        tb_str = traceback.format_exc()
        print(f"Error getting newly added files: {tb_str}")
        raise HTTPException(status_code=500, detail=str(e))
