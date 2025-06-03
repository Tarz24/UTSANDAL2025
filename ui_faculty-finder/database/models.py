import sqlite3
import json
import logging
from datetime import datetime
from typing import List, Dict, Optional, Union
import os

class DatabaseManager:
    """Database manager untuk UI Faculty Finder"""
    
    def __init__(self, db_path: str):
        self.db_path = db_path
        self.logger = logging.getLogger(__name__)
        self.init_database()
    
    def init_database(self):
        """Initialize database dengan membuat tabel-tabel yang diperlukan"""
        try:
            os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
            
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                cursor.execute('PRAGMA foreign_keys = ON')
                
                cursor.execute('''
                    CREATE TABLE IF NOT EXISTS faculties (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        name TEXT NOT NULL,
                        url TEXT UNIQUE NOT NULL,
                        description TEXT,
                        faculty_type TEXT DEFAULT 'general',
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                ''')
                
                cursor.execute('''
                    CREATE TABLE IF NOT EXISTS programs (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        faculty_id INTEGER,
                        name TEXT NOT NULL,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        FOREIGN KEY (faculty_id) REFERENCES faculties (id) ON DELETE CASCADE
                    )
                ''')
                
                cursor.execute('''
                    CREATE TABLE IF NOT EXISTS departments (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        faculty_id INTEGER,
                        name TEXT NOT NULL,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        FOREIGN KEY (faculty_id) REFERENCES faculties (id) ON DELETE CASCADE
                    )
                ''')
                
                cursor.execute('''
                    CREATE TABLE IF NOT EXISTS contacts (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        faculty_id INTEGER UNIQUE,
                        email TEXT,
                        phone TEXT,
                        address TEXT,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        FOREIGN KEY (faculty_id) REFERENCES faculties (id) ON DELETE CASCADE
                    )
                ''')
                
                cursor.execute('''
                    CREATE TABLE IF NOT EXISTS routes (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        faculty_id INTEGER,
                        step_order INTEGER,
                        name TEXT NOT NULL,
                        url TEXT NOT NULL,
                        FOREIGN KEY (faculty_id) REFERENCES faculties (id) ON DELETE CASCADE
                    )
                ''')
                
                cursor.execute('''
                    CREATE TABLE IF NOT EXISTS crawl_metadata (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        base_url TEXT,
                        timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        total_faculties INTEGER DEFAULT 0,
                        pages_crawled INTEGER DEFAULT 0,
                        crawl_duration INTEGER DEFAULT 0,
                        status TEXT DEFAULT 'completed'
                    )
                ''')
                
                cursor.execute('''
                    CREATE TABLE IF NOT EXISTS search_index (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        faculty_id INTEGER,
                        content_type TEXT,
                        content TEXT,
                        keywords TEXT,
                        FOREIGN KEY (faculty_id) REFERENCES faculties (id) ON DELETE CASCADE
                    )
                ''')
                
                cursor.execute('''CREATE INDEX IF NOT EXISTS idx_faculties_name ON faculties(name)''')
                cursor.execute('''CREATE INDEX IF NOT EXISTS idx_faculties_type ON faculties(faculty_type)''')
                cursor.execute('''CREATE INDEX IF NOT EXISTS idx_search_keywords ON search_index(keywords)''')
                cursor.execute('''CREATE INDEX IF NOT EXISTS idx_search_content ON search_index(content)''')
                
                conn.commit()
                self.logger.info("Database initialized successfully")
                
        except sqlite3.Error as e:
            self.logger.error(f"Error initializing database: {e}")
            raise


class Faculty:
    """Model untuk fakultas"""
    
    def __init__(self, db_manager: DatabaseManager):
        self.db = db_manager
        self.logger = logging.getLogger(__name__)
    
    def create(self, faculty_data: Dict) -> Optional[int]:
        """Membuat record fakultas baru"""
        try:
            with sqlite3.connect(self.db.db_path) as conn:
                cursor = conn.cursor()
                
                if not faculty_data.get('name') or not faculty_data.get('url'):
                    self.logger.warning(f"Missing required data: name={faculty_data.get('name')}, url={faculty_data.get('url')}")
                    return None
                
                cursor.execute('''
                    INSERT OR IGNORE INTO faculties (name, url, description, faculty_type)
                    VALUES (?, ?, ?, ?)
                ''', (
                    faculty_data.get('name', '').strip(),
                    faculty_data.get('url', '').strip(),
                    faculty_data.get('description', '').strip(),
                    faculty_data.get('faculty_type', 'general')
                ))
                
                faculty_id = cursor.lastrowid
                
                if faculty_id == 0:
                    cursor.execute('SELECT id FROM faculties WHERE url = ?', (faculty_data.get('url', '').strip(),))
                    result = cursor.fetchone()
                    if result:
                        faculty_id = result[0]
                    else:
                        self.logger.error("Failed to get faculty ID")
                        return None
                
                cursor.execute('DELETE FROM programs WHERE faculty_id = ?', (faculty_id,))
                cursor.execute('DELETE FROM departments WHERE faculty_id = ?', (faculty_id,))
                cursor.execute('DELETE FROM routes WHERE faculty_id = ?', (faculty_id,))
                cursor.execute('DELETE FROM search_index WHERE faculty_id = ?', (faculty_id,))
                
                programs = faculty_data.get('programs', [])
                if programs:
                    for program in programs:
                        if program and program.strip():
                            cursor.execute('''
                                INSERT INTO programs (faculty_id, name) VALUES (?, ?)
                            ''', (faculty_id, program.strip()))
                
                departments = faculty_data.get('departments', [])
                if departments:
                    for department in departments:
                        if department and department.strip():
                            cursor.execute('''
                                INSERT INTO departments (faculty_id, name) VALUES (?, ?)
                            ''', (faculty_id, department.strip()))
                
                contact = faculty_data.get('contact', {})
                if contact and any(contact.values()):
                    cursor.execute('''
                        INSERT OR REPLACE INTO contacts (faculty_id, email, phone, address)
                        VALUES (?, ?, ?, ?)
                    ''', (
                        faculty_id,
                        contact.get('email', '').strip() if contact.get('email') else None,
                        contact.get('phone', '').strip() if contact.get('phone') else None,
                        contact.get('address', '').strip() if contact.get('address') else None
                    ))
                
                routes = faculty_data.get('route', [])
                if routes:
                    for i, route_step in enumerate(routes):
                        if route_step and route_step.get('name'):
                            cursor.execute('''
                                INSERT INTO routes (faculty_id, step_order, name, url)
                                VALUES (?, ?, ?, ?)
                            ''', (
                                faculty_id,
                                i,
                                route_step.get('name', '').strip(),
                                route_step.get('url', '').strip()
                            ))
                
                self._create_search_index(cursor, faculty_id, faculty_data)
                
                cursor.execute('''
                    UPDATE faculties SET updated_at = CURRENT_TIMESTAMP WHERE id = ?
                ''', (faculty_id,))
                
                conn.commit()
                return faculty_id
                
        except sqlite3.Error as e:
            self.logger.error(f"Database error creating faculty: {e}")
            return None
        except Exception as e:
            self.logger.error(f"Unexpected error creating faculty: {e}")
            return None
    
    def _create_search_index(self, cursor, faculty_id: int, faculty_data: Dict):
        """Membuat index untuk pencarian"""
        try:
            name = faculty_data.get('name', '').strip()
            if name:
                cursor.execute('''
                    INSERT INTO search_index (faculty_id, content_type, content, keywords)
                    VALUES (?, ?, ?, ?)
                ''', (
                    faculty_id,
                    'name',
                    name,
                    self._extract_keywords(name)
                ))
            
            description = faculty_data.get('description', '').strip()
            if description:
                cursor.execute('''
                    INSERT INTO search_index (faculty_id, content_type, content, keywords)
                    VALUES (?, ?, ?, ?)
                ''', (
                    faculty_id,
                    'description',
                    description,
                    self._extract_keywords(description)
                ))
            
            programs = faculty_data.get('programs', [])
            for program in programs:
                if program and program.strip():
                    cursor.execute('''
                        INSERT INTO search_index (faculty_id, content_type, content, keywords)
                        VALUES (?, ?, ?, ?)
                    ''', (
                        faculty_id,
                        'program',
                        program.strip(),
                        self._extract_keywords(program)
                    ))
            
            departments = faculty_data.get('departments', [])
            for department in departments:
                if department and department.strip():
                    cursor.execute('''
                        INSERT INTO search_index (faculty_id, content_type, content, keywords)
                        VALUES (?, ?, ?, ?)
                    ''', (
                        faculty_id,
                        'department',
                        department.strip(),
                        self._extract_keywords(department)
                    ))
                    
        except sqlite3.Error as e:
            self.logger.error(f"Error creating search index: {e}")
    
    def _extract_keywords(self, text: str) -> str:
        """Ekstrak kata kunci dari teks untuk indexing"""
        if not text:
            return ""
        
        import re
        words = re.findall(r'\b\w+\b', text.lower())
        
        stopwords = {
            'dan', 'atau', 'yang', 'dari', 'di', 'ke', 'pada', 'untuk', 'dengan', 
            'adalah', 'ini', 'itu', 'the', 'of', 'and', 'in', 'to', 'for', 'with'
        }
        keywords = [word for word in words if len(word) > 2 and word not in stopwords]
        
        return ' '.join(set(keywords))
    
    def get_by_id(self, faculty_id: int) -> Optional[Dict]:
        """Ambil fakultas berdasarkan ID dengan data lengkap"""
        try:
            with sqlite3.connect(self.db.db_path) as conn:
                conn.row_factory = sqlite3.Row
                cursor = conn.cursor()
                
                cursor.execute('SELECT * FROM faculties WHERE id = ?', (faculty_id,))
                faculty_row = cursor.fetchone()
                
                if not faculty_row:
                    return None
                
                faculty = dict(faculty_row)
                
                cursor.execute('SELECT name FROM programs WHERE faculty_id = ? ORDER BY name', (faculty_id,))
                faculty['programs'] = [row['name'] for row in cursor.fetchall()]
                
                cursor.execute('SELECT name FROM departments WHERE faculty_id = ? ORDER BY name', (faculty_id,))
                faculty['departments'] = [row['name'] for row in cursor.fetchall()]
                
                cursor.execute('SELECT email, phone, address FROM contacts WHERE faculty_id = ?', (faculty_id,))
                contact_row = cursor.fetchone()
                if contact_row:
                    faculty['contact'] = {
                        'email': contact_row['email'],
                        'phone': contact_row['phone'],
                        'address': contact_row['address']
                    }
                else:
                    faculty['contact'] = {}
                
                cursor.execute('''
                    SELECT name, url FROM routes WHERE faculty_id = ? ORDER BY step_order
                ''', (faculty_id,))
                faculty['route'] = [{'name': row['name'], 'url': row['url']} for row in cursor.fetchall()]
                
                return faculty
                
        except sqlite3.Error as e:
            self.logger.error(f"Error getting faculty by ID {faculty_id}: {e}")
            return None
    
    def search(self, query: str, limit: int = 20) -> List[Dict]:
        """Pencarian fakultas berdasarkan query dengan scoring"""
        try:
            with sqlite3.connect(self.db.db_path) as conn:
                conn.row_factory = sqlite3.Row
                cursor = conn.cursor()
                
                if not query or not query.strip():
                    return self.get_all(limit=limit)
                
                search_pattern = f"%{query.lower().strip()}%"
                
                search_sql = '''
                    SELECT DISTINCT f.*, 
                           (CASE WHEN LOWER(f.name) LIKE ? THEN 10 ELSE 0 END +
                            CASE WHEN LOWER(f.description) LIKE ? THEN 5 ELSE 0 END +
                            CASE WHEN EXISTS(SELECT 1 FROM programs p WHERE p.faculty_id = f.id AND LOWER(p.name) LIKE ?) THEN 8 ELSE 0 END +
                            CASE WHEN EXISTS(SELECT 1 FROM departments d WHERE d.faculty_id = f.id AND LOWER(d.name) LIKE ?) THEN 6 ELSE 0 END +
                            CASE WHEN EXISTS(SELECT 1 FROM search_index si WHERE si.faculty_id = f.id AND LOWER(si.keywords) LIKE ?) THEN 3 ELSE 0 END
                           ) as relevance_score
                    FROM faculties f
                    WHERE LOWER(f.name) LIKE ? 
                       OR LOWER(f.description) LIKE ?
                       OR EXISTS(SELECT 1 FROM programs p WHERE p.faculty_id = f.id AND LOWER(p.name) LIKE ?)
                       OR EXISTS(SELECT 1 FROM departments d WHERE d.faculty_id = f.id AND LOWER(d.name) LIKE ?)
                       OR EXISTS(SELECT 1 FROM search_index si WHERE si.faculty_id = f.id AND LOWER(si.keywords) LIKE ?)
                    HAVING relevance_score > 0
                    ORDER BY relevance_score DESC, f.name ASC
                    LIMIT ?
                '''
                
                params = [search_pattern] * 10 + [limit]
                cursor.execute(search_sql, params)
                
                results = []
                for row in cursor.fetchall():
                    faculty = dict(row)
                    
                    cursor.execute('SELECT COUNT(*) as count FROM programs WHERE faculty_id = ?', (faculty['id'],))
                    faculty['programs_count'] = cursor.fetchone()['count']
                    
                    cursor.execute('SELECT COUNT(*) as count FROM departments WHERE faculty_id = ?', (faculty['id'],))
                    faculty['departments_count'] = cursor.fetchone()['count']
                    
                    cursor.execute('SELECT name FROM programs WHERE faculty_id = ? LIMIT 3', (faculty['id'],))
                    faculty['sample_programs'] = [row['name'] for row in cursor.fetchall()]
                    
                    cursor.execute('SELECT name FROM departments WHERE faculty_id = ? LIMIT 3', (faculty['id'],))
                    faculty['sample_departments'] = [row['name'] for row in cursor.fetchall()]
                    
                    results.append(faculty)
                
                return results
                
        except sqlite3.Error as e:
            self.logger.error(f"Database error searching faculties: {e}")
            return []
        except Exception as e:
            self.logger.error(f"Unexpected error searching faculties: {e}")
            return []
    
    def get_all(self, limit: int = None, offset: int = 0) -> List[Dict]:
        """Ambil semua fakultas dengan pagination"""
        try:
            with sqlite3.connect(self.db.db_path) as conn:
                conn.row_factory = sqlite3.Row
                cursor = conn.cursor()
                
                query = 'SELECT * FROM faculties ORDER BY name ASC'
                params = []
                
                if limit:
                    query += ' LIMIT ? OFFSET ?'
                    params.extend([limit, offset])
                
                cursor.execute(query, params)
                results = []
                
                for row in cursor.fetchall():
                    faculty = dict(row)
                    
                    cursor.execute('SELECT COUNT(*) as count FROM programs WHERE faculty_id = ?', (faculty['id'],))
                    faculty['programs_count'] = cursor.fetchone()['count']
                    
                    cursor.execute('SELECT COUNT(*) as count FROM departments WHERE faculty_id = ?', (faculty['id'],))
                    faculty['departments_count'] = cursor.fetchone()['count']
                    
                    results.append(faculty)
                
                return results
                
        except sqlite3.Error as e:
            self.logger.error(f"Error getting all faculties: {e}")
            return []
    
    def count(self) -> int:
        """Hitung total fakultas"""
        try:
            with sqlite3.connect(self.db.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute('SELECT COUNT(*) FROM faculties')
                return cursor.fetchone()[0]
        except sqlite3.Error as e:
            self.logger.error(f"Error counting faculties: {e}")
            return 0
    
    def bulk_insert(self, faculties_data: List[Dict]) -> Dict:
        """Insert multiple faculties sekaligus"""
        results = {
            'success': 0,
            'failed': 0,
            'errors': []
        }
        
        for i, faculty_data in enumerate(faculties_data):
            try:
                faculty_id = self.create(faculty_data)
                if faculty_id:
                    results['success'] += 1
                else:
                    results['failed'] += 1
                    results['errors'].append(f"Failed to insert: {faculty_data.get('name', 'Unknown')}")
                    
            except Exception as e:
                results['failed'] += 1
                error_msg = f"Error inserting {faculty_data.get('name', 'Unknown')}: {str(e)}"
                results['errors'].append(error_msg)
                self.logger.error(error_msg)
        
        return results
    
    def delete_by_id(self, faculty_id: int) -> bool:
        """Hapus fakultas berdasarkan ID"""
        try:
            with sqlite3.connect(self.db.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute('DELETE FROM faculties WHERE id = ?', (faculty_id,))
                deleted = cursor.rowcount > 0
                conn.commit()
                return deleted
                
        except sqlite3.Error as e:
            self.logger.error(f"Error deleting faculty {faculty_id}: {e}")
            return False


class CrawlMetadata:
    """Model untuk metadata crawling"""
    
    def __init__(self, db_manager: DatabaseManager):
        self.db = db_manager
        self.logger = logging.getLogger(__name__)
    
    def create_crawl_record(self, base_url: str, total_faculties: int, pages_crawled: int, duration: int = 0) -> Optional[int]:
        """Buat record crawling baru"""
        try:
            with sqlite3.connect(self.db.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    INSERT INTO crawl_metadata (base_url, total_faculties, pages_crawled, crawl_duration)
                    VALUES (?, ?, ?, ?)
                ''', (base_url, total_faculties, pages_crawled, duration))
                
                crawl_id = cursor.lastrowid
                conn.commit()
                return crawl_id
                
        except sqlite3.Error as e:
            self.logger.error(f"Error creating crawl metadata: {e}")
            return None
    
    def get_latest_crawl(self) -> Optional[Dict]:
        """Ambil metadata crawling terbaru"""
        try:
            with sqlite3.connect(self.db.db_path) as conn:
                conn.row_factory = sqlite3.Row
                cursor = conn.cursor()
                cursor.execute('''
                    SELECT * FROM crawl_metadata ORDER BY timestamp DESC LIMIT 1
                ''')
                row = cursor.fetchone()
                return dict(row) if row else None
                
        except sqlite3.Error as e:
            self.logger.error(f"Error getting latest crawl: {e}")
            return None
    
    def get_all_crawls(self, limit: int = 10) -> List[Dict]:
        """Ambil semua record crawling"""
        try:
            with sqlite3.connect(self.db.db_path) as conn:
                conn.row_factory = sqlite3.Row
                cursor = conn.cursor()
                cursor.execute('''
                    SELECT * FROM crawl_metadata ORDER BY timestamp DESC LIMIT ?
                ''', (limit,))
                return [dict(row) for row in cursor.fetchall()]
                
        except sqlite3.Error as e:
            self.logger.error(f"Error getting all crawls: {e}")
            return []


def create_models(db_path: str):
    """Factory function untuk membuat instance models"""
    db_manager = DatabaseManager(db_path)
    return {
        'faculty': Faculty(db_manager),
        'crawl_metadata': CrawlMetadata(db_manager),
        'db_manager': db_manager
    }