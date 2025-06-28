import os
import hashlib
import json
import PyPDF2
from docx import Document
from .EDA_Cleaner import TextPipeline, TextCleaner
import logging

logger = logging.getLogger(__name__)

class FileProcessor:
    def __init__(self, chunk_size=850, chunk_overlap=130):
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap
        self.processed_hashes = set()

    def calculate_hash(self, content):
        return hashlib.sha256(content.encode('utf-8')).hexdigest()

    def read_file(self, file_path):
        file_extension = os.path.splitext(file_path)[1].lower()
        content = ""
        try:
            if file_extension == '.txt':
                with open(file_path, 'r', encoding='utf-8') as file:
                    content = file.read()
            elif file_extension == '.pdf':
                with open(file_path, 'rb') as file:
                    pdf_reader = PyPDF2.PdfReader(file)
                    for page in pdf_reader.pages:
                        content += page.extract_text() + "\n"
            elif file_extension == '.docx':
                doc = Document(file_path)
                for para in doc.paragraphs:
                    content += para.text + "\n"
            elif file_extension == '.json':
                with open(file_path, 'r', encoding='utf-8') as file:
                    data = json.load(file)
                    content = json.dumps(data, ensure_ascii=False)
            else:
                raise ValueError(f"Type de fichier non pris en charge : {file_extension}")
            return content.strip()
        except Exception as e:
            raise Exception(f"Erreur lors de la lecture du fichier {file_path} : {str(e)}")

    def split_into_chunks(self, text):
        if not text:
            return []
        chunks = []
        start = 0
        text_length = len(text)
        while start < text_length:
            end = start + self.chunk_size
            chunk = text[start:end].strip()
            if chunk:
                chunks.append(chunk)
            start += self.chunk_size - self.chunk_overlap
        return chunks

    def process_file(self, file_path, force_reprocess=False):
        """
        Process a file and return chunks and hash
        
        Args:
            file_path: Path to the file
            force_reprocess: If True, reprocess even if already processed
            
        Returns:
            Tuple of (chunks, file_hash) or (None, file_hash) if already processed
        """
        try:
            content = self.read_file(file_path)
            file_hash = self.calculate_hash(content)
            
            if not force_reprocess and file_hash in self.processed_hashes:
                logger.info(f"File {file_path} already processed (hash: {file_hash})")
                return None, file_hash
            
            self.processed_hashes.add(file_hash)
            
            # Clean the content
            cleaner = TextCleaner()
            pipeline = TextPipeline(cleaner)
            cleaned_content = pipeline.process(content)
            
            # Split into chunks
            chunks = self.split_into_chunks(cleaned_content)
            
            logger.info(f"Processed file {file_path}: {len(chunks)} chunks created")
            return chunks, file_hash
            
        except Exception as e:
            logger.error(f"Error processing file {file_path}: {e}")
            raise

    def clear_processed_hashes(self):
        """Clear the set of processed hashes"""
        self.processed_hashes.clear()
        
    def remove_from_processed(self, file_hash):
        """Remove a specific hash from processed hashes"""
        self.processed_hashes.discard(file_hash)