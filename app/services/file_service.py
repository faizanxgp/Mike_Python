"""
File Service - Business logic for file operations
Handles file upload, processing, preview generation, and management
"""

import os
import shutil
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Optional
import mimetypes
import fitz  # PyMuPDF
from PIL import Image
from fastapi import HTTPException, UploadFile
from fastapi.responses import FileResponse, JSONResponse

from app.core.config import REMOTE_DIR, BACKUP_DIR, PREVIEW_DIR


class FileService:
    """Service class for file operations"""
    
    def __init__(self):
        self.allowed_extensions = {
            '.pdf', '.doc', '.docx', '.xls', '.xlsx', '.ppt', '.pptx',
            '.txt', '.csv', '.jpg', '.jpeg', '.png', '.gif', '.bmp', '.tiff'
        }
        self.max_file_size = 100 * 1024 * 1024  # 100MB
    
    async def upload_files(self, files: List[UploadFile], current_user: dict) -> Dict:
        """Upload multiple files with validation"""
        try:
            uploaded_files = []
            
            for file in files:
                # Validate file
                if not self._is_allowed_file(file.filename):
                    raise HTTPException(
                        status_code=400, 
                        detail=f"File type not allowed: {file.filename}"
                    )
                
                # Check file size
                file_content = await file.read()
                if len(file_content) > self.max_file_size:
                    raise HTTPException(
                        status_code=413,
                        detail=f"File too large: {file.filename}"
                    )
                
                # Create safe filename
                safe_filename = self._create_safe_filename(file.filename)
                file_path = os.path.join(REMOTE_DIR, safe_filename)
                
                # Save file
                with open(file_path, "wb") as buffer:
                    buffer.write(file_content)
                
                uploaded_files.append({
                    "filename": safe_filename,
                    "original_name": file.filename,
                    "size": len(file_content),
                    "mimetype": file.content_type,
                    "uploaded_at": datetime.now().isoformat(),
                    "uploaded_by": current_user.get("preferred_username", "unknown")
                })
                
                # Reset file pointer for potential reuse
                await file.seek(0)
            
            return {
                "message": f"Successfully uploaded {len(uploaded_files)} files",
                "files": uploaded_files,
                "total_size": sum(f["size"] for f in uploaded_files)
            }
        
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Upload failed: {str(e)}")
    
    async def list_files(self) -> Dict:
        """List all files with metadata"""
        try:
            files = []
            total_size = 0
            
            for filename in os.listdir(REMOTE_DIR):
                file_path = os.path.join(REMOTE_DIR, filename)
                if os.path.isfile(file_path):
                    stat = os.stat(file_path)
                    files.append({
                        "filename": filename,
                        "size": stat.st_size,
                        "modified": datetime.fromtimestamp(stat.st_mtime).isoformat(),
                        "created": datetime.fromtimestamp(stat.st_ctime).isoformat(),
                        "mimetype": mimetypes.guess_type(filename)[0],
                        "extension": Path(filename).suffix.lower()
                    })
                    total_size += stat.st_size
            
            # Sort by modification date (newest first)
            files.sort(key=lambda x: x["modified"], reverse=True)
            
            return {
                "files": files,
                "total": len(files),
                "total_size": total_size
            }
        
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Failed to list files: {str(e)}")
    
    async def search_files(self, query: str) -> Dict:
        """Search files by name"""
        try:
            all_files = await self.list_files()
            query_lower = query.lower()
            
            matching_files = [
                file for file in all_files["files"]
                if query_lower in file["filename"].lower()
            ]
            
            return {
                "files": matching_files,
                "total": len(matching_files),
                "query": query
            }
        
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Search failed: {str(e)}")
    
    async def download_file(self, filename: str) -> FileResponse:
        """Download a specific file"""
        file_path = os.path.join(REMOTE_DIR, filename)
        
        if not os.path.exists(file_path):
            raise HTTPException(status_code=404, detail="File not found")
        
        return FileResponse(
            path=file_path,
            filename=filename,
            media_type='application/octet-stream'
        )
    
    async def preview_file(self, filename: str, page: int = 1) -> Dict:
        """Generate file preview"""
        file_path = os.path.join(REMOTE_DIR, filename)
        
        if not os.path.exists(file_path):
            raise HTTPException(status_code=404, detail="File not found")
        
        file_ext = Path(filename).suffix.lower()
        
        try:
            if file_ext == '.pdf':
                return await self._preview_pdf(file_path, page)
            elif file_ext in ['.jpg', '.jpeg', '.png', '.gif', '.bmp', '.tiff']:
                return await self._preview_image(file_path)
            else:
                return {"message": "Preview not available for this file type"}
        
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Preview generation failed: {str(e)}")
    
    async def delete_file(self, filename: str) -> Dict:
        """Delete a specific file"""
        file_path = os.path.join(REMOTE_DIR, filename)
        
        if not os.path.exists(file_path):
            raise HTTPException(status_code=404, detail="File not found")
        
        try:
            # Move to backup before deletion
            backup_path = os.path.join(BACKUP_DIR, f"{datetime.now().strftime('%Y%m%d_%H%M%S')}_{filename}")
            shutil.move(file_path, backup_path)
            
            return {
                "message": f"File {filename} deleted successfully",
                "backed_up_to": backup_path
            }
        
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Failed to delete file: {str(e)}")
    
    async def get_file_info(self, filename: str) -> Dict:
        """Get detailed file information"""
        file_path = os.path.join(REMOTE_DIR, filename)
        
        if not os.path.exists(file_path):
            raise HTTPException(status_code=404, detail="File not found")
        
        try:
            stat = os.stat(file_path)
            file_ext = Path(filename).suffix.lower()
            
            info = {
                "filename": filename,
                "size": stat.st_size,
                "size_human": self._human_readable_size(stat.st_size),
                "modified": datetime.fromtimestamp(stat.st_mtime).isoformat(),
                "created": datetime.fromtimestamp(stat.st_ctime).isoformat(),
                "mimetype": mimetypes.guess_type(filename)[0],
                "extension": file_ext,
                "path": file_path
            }
            
            # Add specific info for PDFs
            if file_ext == '.pdf':
                info.update(await self._get_pdf_info(file_path))
            
            return info
        
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Failed to get file info: {str(e)}")
    
    def _is_allowed_file(self, filename: str) -> bool:
        """Check if file extension is allowed"""
        return Path(filename).suffix.lower() in self.allowed_extensions
    
    def _create_safe_filename(self, filename: str) -> str:
        """Create a safe filename by replacing spaces and special characters"""
        safe_name = filename.replace(" ", "_")
        # Add timestamp if file exists
        base_path = os.path.join(REMOTE_DIR, safe_name)
        if os.path.exists(base_path):
            name, ext = os.path.splitext(safe_name)
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            safe_name = f"{name}_{timestamp}{ext}"
        
        return safe_name
    
    def _human_readable_size(self, size_bytes: int) -> str:
        """Convert bytes to human readable format"""
        for unit in ['B', 'KB', 'MB', 'GB']:
            if size_bytes < 1024.0:
                return f"{size_bytes:.1f} {unit}"
            size_bytes /= 1024.0
        return f"{size_bytes:.1f} TB"
    
    async def _preview_pdf(self, file_path: str, page: int) -> Dict:
        """Generate PDF preview"""
        try:
            doc = fitz.open(file_path)
            if page < 1 or page > len(doc):
                raise HTTPException(status_code=400, detail="Invalid page number")
            
            page_obj = doc[page - 1]
            pix = page_obj.get_pixmap()
            img_data = pix.tobytes("png")
            
            # Save preview
            preview_filename = f"preview_{Path(file_path).stem}_page_{page}.png"
            preview_path = os.path.join(PREVIEW_DIR, preview_filename)
            
            with open(preview_path, "wb") as f:
                f.write(img_data)
            
            doc.close()
            
            return {
                "preview_path": preview_path,
                "page": page,
                "total_pages": len(doc),
                "preview_filename": preview_filename
            }
        
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"PDF preview failed: {str(e)}")
    
    async def _preview_image(self, file_path: str) -> Dict:
        """Generate image preview (thumbnail)"""
        try:
            with Image.open(file_path) as img:
                # Create thumbnail
                img.thumbnail((800, 600), Image.Resampling.LANCZOS)
                
                preview_filename = f"thumb_{Path(file_path).stem}.jpg"
                preview_path = os.path.join(PREVIEW_DIR, preview_filename)
                
                img.save(preview_path, "JPEG", quality=85)
                
                return {
                    "preview_path": preview_path,
                    "preview_filename": preview_filename,
                    "original_size": os.path.getsize(file_path)
                }
        
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Image preview failed: {str(e)}")
    
    async def _get_pdf_info(self, file_path: str) -> Dict:
        """Get PDF specific information"""
        try:
            doc = fitz.open(file_path)
            metadata = doc.metadata
            
            info = {
                "pages": len(doc),
                "title": metadata.get("title", ""),
                "author": metadata.get("author", ""),
                "subject": metadata.get("subject", ""),
                "creator": metadata.get("creator", ""),
                "producer": metadata.get("producer", ""),
                "created": metadata.get("creationDate", ""),
                "modified": metadata.get("modDate", "")
            }
            
            doc.close()
            return info
        
        except Exception:
            return {"pages": 0, "error": "Could not read PDF metadata"}
