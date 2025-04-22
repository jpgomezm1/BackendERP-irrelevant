import os
import uuid
import logging
from werkzeug.utils import secure_filename
from flask import current_app

def get_file_path(filename):
    """
    Get the full file path for a stored file
    
    Args:
        filename (str): The filename to get the path for
        
    Returns:
        str: The full file path
    """
    return os.path.join(current_app.config['UPLOAD_FOLDER'], filename)

def save_file(file_storage):
    """
    Save a file from a FileStorage object with a secure unique name
    
    Args:
        file_storage: The FileStorage object from a form upload
        
    Returns:
        str: The saved filename
    """
    if not file_storage:
        return None
        
    # Ensure upload directory exists
    os.makedirs(current_app.config['UPLOAD_FOLDER'], exist_ok=True)
    
    # Get original filename and extension
    original_filename = secure_filename(file_storage.filename)
    extension = original_filename.rsplit('.', 1)[1].lower() if '.' in original_filename else ''
    
    # Generate unique filename
    unique_filename = f"{uuid.uuid4().hex}.{extension}" if extension else f"{uuid.uuid4().hex}"
    
    # Save the file
    file_path = os.path.join(current_app.config['UPLOAD_FOLDER'], unique_filename)
    file_storage.save(file_path)
    
    logging.debug(f"File saved: {file_path}")
    
    return unique_filename

def delete_file(filename):
    """
    Delete a file by filename
    
    Args:
        filename (str): The filename to delete
        
    Returns:
        bool: True if deletion successful, False otherwise
    """
    if not filename:
        return False
        
    file_path = get_file_path(filename)
    
    if os.path.exists(file_path):
        try:
            os.remove(file_path)
            logging.debug(f"File deleted: {file_path}")
            return True
        except Exception as e:
            logging.error(f"Error deleting file {file_path}: {str(e)}")
            return False
    else:
        logging.warning(f"File not found for deletion: {file_path}")
        return False
