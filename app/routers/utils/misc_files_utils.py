import ctypes
from ctypes import wintypes
import os
from pathlib import Path
import datetime
import shutil
import traceback


def _get_owner_windows(path: str) -> str:
    """
    Uses Win32 API calls (via ctypes) to resolve the owner of a file/folder.
    Returns "DOMAIN\\User" on success, or raises an exception on failure.
    """
    # Constants
    SE_FILE_OBJECT = 1
    OWNER_SECURITY_INFORMATION = 1

    # Prepare GetNamedSecurityInfoW
    advapi32 = ctypes.windll.advapi32
    GetNamedSecurityInfoW = advapi32.GetNamedSecurityInfoW
    GetNamedSecurityInfoW.restype = wintypes.DWORD
    GetNamedSecurityInfoW.argtypes = [
        wintypes.LPWSTR,    # pObjectName
        wintypes.DWORD,     # ObjectType
        wintypes.DWORD,     # SecurityInfo
        ctypes.POINTER(ctypes.c_void_p),  # ppsidOwner
        ctypes.POINTER(ctypes.c_void_p),  # ppsidGroup
        ctypes.POINTER(ctypes.c_void_p),  # ppDacl
        ctypes.POINTER(ctypes.c_void_p),  # ppSacl
        ctypes.POINTER(ctypes.c_void_p)   # ppSecurityDescriptor
    ]

    owner_sid = ctypes.c_void_p()
    # We don’t need group/pDacl/pSacl, so pass None for those pointers,
    # but we do need a place to store the returned SECURITY_DESCRIPTOR so we can free it later.
    pSecurityDescriptor = ctypes.c_void_p()

    # Call GetNamedSecurityInfoW to get an owner SID pointer
    result = GetNamedSecurityInfoW(
        ctypes.c_wchar_p(path),
        SE_FILE_OBJECT,
        OWNER_SECURITY_INFORMATION,
        ctypes.byref(owner_sid),
        None,
        None,
        None,
        ctypes.byref(pSecurityDescriptor)
    )
    if result != 0:
        # Non‐zero return code → Win32 error
        raise ctypes.WinError(result)

    try:
        # Now call LookupAccountSidW to turn that SID into a “DOMAIN\\Username” string
        LookupAccountSidW = advapi32.LookupAccountSidW
        LookupAccountSidW.restype = wintypes.BOOL
        LookupAccountSidW.argtypes = [
            wintypes.LPCWSTR,  # lpSystemName (None for local machine)
            wintypes.LPVOID,   # Sid
            wintypes.LPWSTR,   # Name buffer
            ctypes.POINTER(wintypes.DWORD),  # cchName
            wintypes.LPWSTR,   # Domain buffer
            ctypes.POINTER(wintypes.DWORD),  # cchDomain
            ctypes.POINTER(wintypes.DWORD)   # peUse
        ]

        # First call to get required buffer sizes
        name_len = wintypes.DWORD(0)
        domain_len = wintypes.DWORD(0)
        peUse = wintypes.DWORD()
        # This call is expected to fail with ERROR_INSUFFICIENT_BUFFER (122),
        # but it will fill in name_len and domain_len for us
        LookupAccountSidW(
            None,
            owner_sid,
            None,
            ctypes.byref(name_len),
            None,
            ctypes.byref(domain_len),
            ctypes.byref(peUse)
        )

        # Allocate buffers of the needed size:
        name_buf = ctypes.create_unicode_buffer(name_len.value)
        domain_buf = ctypes.create_unicode_buffer(domain_len.value)

        success = LookupAccountSidW(
            None,
            owner_sid,
            name_buf,
            ctypes.byref(name_len),
            domain_buf,
            ctypes.byref(domain_len),
            ctypes.byref(peUse)
        )
        if not success:
            raise ctypes.WinError(ctypes.get_last_error())

        return f"{domain_buf.value}\\{name_buf.value}"
    finally:
        # Free the SECURITY_DESCRIPTOR that GetNamedSecurityInfoW allocated
        if pSecurityDescriptor:
            # LocalFree is the correct way to free this pointer
            ctypes.windll.kernel32.LocalFree(pSecurityDescriptor)


def get_owner(path: str) -> str:
    """
    Cross‐platform owner lookup:
    - On Windows: try the Win32/ctypes routine above.
    - On Unix‐like: just call Path(path).owner().
    If anything fails, return "UNKNOWN".
    """
    try:
        if os.name == "nt":
            # On Windows:
            return _get_owner_windows(path)
        else:
            # On Unix‐like:
            return Path(path).owner()
    except Exception:
        return "UNKNOWN"


def search_files_and_folders(root, query, case_sensitive=False):
    """
    Recursively search under `root` for any file or folder whose name contains `query`.
    Returns a list of full paths to matching files/folders.
    
    - root:      string path where search begins (e.g. "." or "C:\\Users\\...")
    - query:     substring to look for in file/folder names    - case_sensitive: if False (default), perform a case-insensitive match
    """
    matches = []
    if not case_sensitive:
        query_lower = query.lower()

    for dirpath, dirnames, filenames in os.walk(root):
        # check folders
        for dirname in dirnames:
            name_to_check = dirname if case_sensitive else dirname.lower()
            if (query in dirname) if case_sensitive else (query_lower in name_to_check):
                found_path = os.path.join(dirpath, dirname)
                base_dir = os.path.normpath(os.path.join(os.getcwd(), "remote"))
                relative_path = os.path.relpath(found_path, base_dir)
                # Convert backslashes to forward slashes for cross-platform compatibility
                relative_path = relative_path.replace(os.sep, '/')
                matches.append(relative_path)

        # check files
        for filename in filenames:
            name_to_check = filename if case_sensitive else filename.lower()
            if (query in filename) if case_sensitive else (query_lower in name_to_check):
                found_path = os.path.join(dirpath, filename)
                base_dir = os.path.normpath(os.path.join(os.getcwd(), "remote"))
                relative_path = os.path.relpath(found_path, base_dir)
                # Convert backslashes to forward slashes for cross-platform compatibility
                relative_path = relative_path.replace(os.sep, '/')
                matches.append(relative_path)

    return matches


def has_hierarchical_permission(target_path, permissions, roles):
    """
    Check if the target_path has permission based on hierarchical access.
    A user with permission to a parent directory should have access to all subdirectories and files.
    
    Args:
        target_path: The path to check permission for (e.g., 'backup/file.txt')
        permissions: List of permission paths (e.g., ['.', 'docs'])
    
    Returns:
        bool: True if access is granted, False otherwise
    """
    
    if "admin" in roles:
        # If user has admin role, grant access to everything
        return True
    
    # Normalize the target path
    if target_path == '.':
        target_path = ''
    
    for permission in permissions:
        # Normalize permission path
        if permission == '.':
            permission = ''
        
        # Check exact match
        if target_path == permission:
            return True
        
        # Check if permission is a parent directory of target_path
        if permission == '':  # Root permission grants access to everything
            return True
        elif target_path.startswith(permission + '/'):
            return True
        
        # Check if target_path is within the permission directory
        # This handles cases where permission might be 'docs' and target is 'docs/subfolder/file.txt'
        if permission != '' and (target_path == permission or target_path.startswith(permission + '/')):
            return True
    
    return False


async def dir_contents_details(abs_path: str, permissions: list, roles: list):
    try:
        # permissions
        base_dir = os.path.normpath(os.path.join(os.getcwd(), "remote"))
        relative_path = str(Path(os.path.relpath(abs_path, base_dir)).as_posix())
        # print('relative_path:', relative_path)
        # print('permissions:', permissions)
        
        # Modified directory-level permission check:
        # Allow access to a directory if:
        # 1. User has direct permission to this directory, OR
        # 2. User has permission to any subdirectory within this directory (for browsing)
        def can_access_directory(dir_path, perms, roles):
            
            if "admin" in roles:
                print("admin role detected, granting access to all directories")
                return True
            
            # Direct permission to this directory
            if has_hierarchical_permission(dir_path, perms, roles):
                return True
            
            # Check if user has permission to any subdirectory within this directory
            # This allows browsing parent directories to reach permitted subdirectories
            if dir_path == ".":  # Root directory case
                for perm in perms:
                    if perm != "." and not perm.startswith("../"):  # Any non-root permission means they need to browse root
                        return True
            else:
                for perm in perms:
                    if perm.startswith(dir_path + "/"):  # Permission to subdirectory
                        return True
            
            return False
        
        # Check if user can access this directory
        if not can_access_directory(relative_path, permissions, roles):
            return []  # Return empty list if no permission to access this directory
        
        results = []
        for entry in os.listdir(abs_path):
            entry_relative_path = f"{relative_path}/{entry}" if relative_path != '.' else entry
            # print('entry_relative_path:', entry_relative_path)
            
            # Use hierarchical permission checking
            if not has_hierarchical_permission(entry_relative_path, permissions, roles):
                continue
            entry_path = os.path.join(abs_path, entry)
            p = Path(entry_path)
            try:
                st = p.stat()
                size_bytes = st.st_size

                # Cross‐platform owner lookup
                try:
                    owner_name = get_owner(abs_path)
                except Exception:
                    # Fallback if owner() details not available
                    owner_name = "UNKNOWN"

                # Last‐modified as an ISO‐8601 string (UTC)
                last_mod = datetime.datetime.fromtimestamp(
                    st.st_mtime, tz=datetime.timezone.utc
                )
                last_mod_iso = last_mod.isoformat()
                
                num_files = 0
                num_subdirs = 0
                
                if p.is_dir():
                    try:
                        # Count only immediate children (non‐recursive)
                        for child in p.iterdir():
                            if child.is_file():
                                num_files += 1
                            elif child.is_dir():
                                num_subdirs += 1
                    except Exception as inner_err:
                        # If listing fails (permissions, etc.), log and leave counts at 0
                        print(f"    ❗ couldn’t list contents of {entry_path}: {inner_err}")

                results.append({
                    "name": entry,
                    "is_dir": p.is_dir(),
                    "size_bytes": size_bytes,
                    "owner": owner_name,
                    "last_modified": last_mod_iso,
                    "num_files": num_files,
                    "num_subdirs": num_subdirs
                })
            except Exception as file_err:
                # Skip entries that can’t be stat’d or owner() fails unexpectedly
                print(f"  ❗ couldn’t process {entry_path}: {file_err}")
                continue
        
        return results
    
    except Exception as e:
        raise e from e


async def process_directory_structure(structure, base_dir, current_path, file_map, uploaded_files, created_dirs):
    """
    Recursively process directory structure and create directories/files.
    
    Expected structure format:
    {
        "folders": {
            "folder_name": {
                "folders": {...},  # nested folders
                "files": ["file1.txt", "file2.pdf"]  # files in this folder
            }
        },
        "files": ["root_file.txt"]  # files in root
    }
    """
    try:
        # Import here to avoid circular imports
        from app.routers.utils.misc_keycloak_utils import create_resource
        
        # Process files in current directory
        if "files" in structure and structure["files"]:
            for filename in structure["files"]:
                if filename in file_map:
                    file_obj = file_map[filename]
                    
                    # Create the full path for the file
                    relative_file_path = os.path.join(current_path, filename) if current_path else filename
                    abs_file_path = os.path.normpath(os.path.join(base_dir, relative_file_path))
                    
                    # Ensure directory exists
                    os.makedirs(os.path.dirname(abs_file_path), exist_ok=True)
                    
                    # Save the file
                    with open(abs_file_path, "wb") as buffer:
                        shutil.copyfileobj(file_obj.file, buffer)
                    
                    # Create resource in Keycloak
                    relative_file_location = str(Path(relative_file_path).as_posix())
                    # resource_payload = {
                    #     "name": relative_file_location,
                    #     "displayName": relative_file_location,
                    #     "type": "file",
                    #     "icon_uri": "",
                    #     "ownerManagedAccess": False,
                    #     "attributes": {},
                    #     "scopes": []
                    # }
                    # await create_resource(resource_payload)
                    
                    uploaded_files.append(relative_file_location)
                else:
                    print(f"Warning: File {filename} specified in structure but not found in uploaded files")
        
        # Process folders
        if "folders" in structure and structure["folders"]:
            for folder_name, folder_structure in structure["folders"].items():
                # Create the new path
                new_path = os.path.join(current_path, folder_name) if current_path else folder_name
                abs_dir_path = os.path.normpath(os.path.join(base_dir, new_path))
                
                # Create directory
                os.makedirs(abs_dir_path, exist_ok=True)
                
                # Create resource in Keycloak for directory
                relative_dir_path = str(Path(new_path).as_posix())
                # resource_payload = {
                #     "name": relative_dir_path,
                #     "displayName": relative_dir_path,
                #     "type": "dir",
                #     "icon_uri": "",
                #     "ownerManagedAccess": False,
                #     "attributes": {},
                #     "scopes": []
                # }
                # await create_resource(resource_payload)
                
                created_dirs.append(relative_dir_path)
                
                # Recursively process subdirectory
                await process_directory_structure(
                    folder_structure, 
                    base_dir, 
                    new_path, 
                    file_map, 
                    uploaded_files, 
                    created_dirs
                )
                
    except Exception as e:
        tb_str = traceback.format_exc()
        print(f"Error processing directory structure at path '{current_path}': {tb_str}")
        raise e


async def update_user_recent_file_attribute(user_id: str, username: str, file_path: str):
    """
    Update the user's 'recent_files' attribute in Keycloak with the downloaded file path.
    Appends to existing recent_files list if it exists, otherwise creates a new list.
    """
    from app.routers.utils.api_keycloak_utils import update_user_details, retrieve_user_details
    
    try:
        # First, retrieve current user details to get existing attributes
        user_response = await retrieve_user_details(username)
        
        if user_response.status_code not in [200, 201]:
            print(f"Error retrieving user details from Keycloak: {user_response.status_code} - {user_response.text}")
            return
            
        user_data = user_response.json()[0] if user_response.json() else {}
        current_attributes = user_data.get("attributes", {})
        
        # Get existing recent_files list or create new empty list
        recent_files = current_attributes.get("recent_files", [])
        
        # Create timestamp and new entry with timestamp|file_path format
        timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        new_entry = f"{timestamp}|{file_path}"
        
        # Remove any existing entry for this file path (check by file path part after |)
        recent_files = [entry for entry in recent_files if not entry.endswith(f"|{file_path}")]
        
        # Append the new entry to the list
        recent_files.append(new_entry)
        
        max_entries = 2
        if len(recent_files) > max_entries:
            # Sort by timestamp (first part before |) in chronological order
            recent_files.sort(key=lambda x: x.split('|')[0])
            # Keep only the last 5 entries (most recent)
            recent_files = recent_files[-max_entries:]
        
        # Update the attributes with the new recent_files list
        updated_attributes = current_attributes.copy()
        updated_attributes["recent_files"] = recent_files
        
        # Prepare payload with all existing user data plus updated attributes
        payload = {
            "username": user_data.get("username", username),  # Use retrieved username or fallback to parameter
            "firstName": user_data.get("firstName", ""),
            "lastName": user_data.get("lastName", ""),
            "email": user_data.get("email", ""),
            "emailVerified": user_data.get("emailVerified", True),
            "enabled": user_data.get("enabled", True),
            "attributes": updated_attributes
        }
        print("/download_file endpoint: Updating user attributes in Keycloak:", payload)
        # Update user attributes in Keycloak
        response = await update_user_details(payload, user_id)
        
        if response.status_code not in [200, 201, 204]:
            print(f"Error updating user attributes in Keycloak: {response.status_code} - {response.text}")
            
    except Exception as e:
        # Log the error but don't fail the download
        print(f"Error updating user attributes in Keycloak for user {user_id}: {str(e)}")


def scan_recently_modified_files(root_dir, cutoff_criteria=3):
    """
    Recursively scan directory structure to find files modified after a certain point.
    
    Args:
        root_dir: Root directory to start scanning from
        cutoff_criteria: Either an integer (days to look back) or a datetime object (cutoff timestamp)
    
    Returns:
        List of dictionaries containing file information:
        [
            {
                "path": "relative/path/to/file.ext",
                "absolute_path": "/full/path/to/file.ext", 
                "last_modified": "2025-07-01T10:30:45+00:00",
                "size_bytes": 1024
            },
            ...
        ]
    """
    recently_modified_files = []
    
    # Determine cutoff time based on the type of cutoff_criteria
    if isinstance(cutoff_criteria, datetime.datetime):
        # If it's already a datetime object, use it directly
        cutoff_time = cutoff_criteria
        # Ensure it has timezone info
        if cutoff_time.tzinfo is None:
            cutoff_time = cutoff_time.replace(tzinfo=datetime.timezone.utc)
    else:
        # If it's an integer (days), calculate cutoff datetime
        days = int(cutoff_criteria)
        cutoff_time = datetime.datetime.now(tz=datetime.timezone.utc) - datetime.timedelta(days=days)
    
    try:
        base_dir = os.path.normpath(os.path.join(os.getcwd(), "remote"))
        
        for dirpath, dirnames, filenames in os.walk(root_dir):
            for filename in filenames:
                file_path = os.path.join(dirpath, filename)
                try:
                    # Get file statistics
                    st = os.stat(file_path)
                    
                    # Convert modification time to UTC datetime
                    file_mod_time = datetime.datetime.fromtimestamp(
                        st.st_mtime, tz=datetime.timezone.utc
                    )
                    
                    # Check if file was modified within the specified time window
                    if file_mod_time >= cutoff_time:
                        # Calculate relative path from the base "remote" directory
                        relative_path = os.path.relpath(file_path, base_dir)
                        # Convert backslashes to forward slashes for cross-platform compatibility
                        relative_path = relative_path.replace(os.sep, '/')
                        
                        recently_modified_files.append({
                            "path": relative_path,
                            "absolute_path": file_path,
                            "last_modified": file_mod_time.isoformat(),
                            "size_bytes": st.st_size
                        })
                        
                except (OSError, PermissionError) as e:
                    # Skip files that can't be accessed
                    print(f"Could not access file {file_path}: {e}")
                    continue
    
    except Exception as e:
        print(f"Error scanning directory {root_dir}: {e}")
        raise e
    
    # Sort by modification time (newest first)
    recently_modified_files.sort(key=lambda x: x["last_modified"], reverse=True)
    
    return recently_modified_files
