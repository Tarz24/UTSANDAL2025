import sqlite3
import re
import logging
import time
from typing import Dict, List, Set, Optional
from collections import Counter
import math
import threading
from contextlib import contextmanager

class SearchIndexer:
    """Indexer untuk membuat dan memelihara search index fakultas dengan handling database lock"""
    
    def __init__(self, db_path: str):
        self.db_path = db_path
        self.logger = logging.getLogger(__name__)
        self._lock = threading.RLock()  # Reentrant lock untuk thread safety
        
        # Indonesian stopwords - diperluas
        self.stopwords = {
            'dan', 'atau', 'yang', 'dari', 'di', 'ke', 'pada', 'untuk', 'dengan', 
            'adalah', 'ini', 'itu', 'akan', 'dapat', 'telah', 'sudah', 'oleh',
            'dalam', 'sebagai', 'menjadi', 'karena', 'jika', 'saat', 'ketika',
            'dimana', 'bagian', 'bagaimana', 'mengapa', 'siapa', 'kapan',
            'sebuah', 'suatu', 'satu', 'dua', 'tiga', 'empat', 'lima',
            'the', 'a', 'an', 'and', 'or', 'but', 'in', 'on', 'at', 'to', 
            'for', 'of', 'with', 'by', 'is', 'are', 'was', 'were', 'be',
            'have', 'has', 'had', 'do', 'does', 'did', 'will', 'would',
            'ada', 'tidak', 'bisa', 'hanya', 'juga', 'lebih', 'sama', 'lain'
        }
        
        # Setup database connection parameters
        self.db_timeout = 30.0  # 30 seconds timeout
        self.max_retries = 3
        
        # Initialize database structure
        self._initialize_database()
    
    @contextmanager
    def get_db_connection(self, timeout=None):
        """Context manager untuk database connection dengan proper handling"""
        timeout = timeout or self.db_timeout
        conn = None
        try:
            with self._lock:
                conn = sqlite3.connect(
                    self.db_path, 
                    timeout=timeout,
                    isolation_level=None  # Autocommit mode
                )
                # Set pragmas for better performance and locking
                conn.execute('PRAGMA journal_mode=WAL')
                conn.execute('PRAGMA synchronous=NORMAL')
                conn.execute('PRAGMA cache_size=10000')
                conn.execute('PRAGMA temp_store=MEMORY')
                conn.execute('PRAGMA busy_timeout=30000')  # 30 seconds
                
                yield conn
        except sqlite3.Error as e:
            self.logger.error(f"Database connection error: {e}")
            if conn:
                conn.rollback()
            raise
        finally:
            if conn:
                try:
                    conn.close()
                except:
                    pass
    
    def _initialize_database(self):
        """Initialize database structure jika belum ada"""
        try:
            with self.get_db_connection() as conn:
                cursor = conn.cursor()
                
                # Create search_index table if not exists
                cursor.execute('''
                    CREATE TABLE IF NOT EXISTS search_index (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        faculty_id INTEGER NOT NULL,
                        content_type TEXT NOT NULL,
                        content TEXT,
                        keywords TEXT,
                        weight REAL DEFAULT 1.0,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        FOREIGN KEY (faculty_id) REFERENCES faculties(id)
                    )
                ''')
                
                # Create indexes for better performance
                indexes = [
                    'CREATE INDEX IF NOT EXISTS idx_search_faculty_id ON search_index(faculty_id)',
                    'CREATE INDEX IF NOT EXISTS idx_search_keywords ON search_index(keywords)',
                    'CREATE INDEX IF NOT EXISTS idx_search_content_type ON search_index(content_type)',
                    'CREATE INDEX IF NOT EXISTS idx_search_weight ON search_index(weight)',
                    'CREATE INDEX IF NOT EXISTS idx_search_composite ON search_index(faculty_id, content_type, keywords)'
                ]
                
                for index_sql in indexes:
                    cursor.execute(index_sql)
                
                self.logger.info("Database structure initialized successfully")
                
        except sqlite3.Error as e:
            self.logger.error(f"Error initializing database: {e}")
    
    def extract_keywords(self, text: str) -> List[str]:
        """Extract dan bersihkan keywords dari teks dengan normalisasi yang lebih baik"""
        if not text:
            return []
        
        # Convert to lowercase
        text = text.lower()
        
        # Replace common abbreviations and normalize
        text = re.sub(r'\bft\b', 'fakultas teknik', text)
        text = re.sub(r'\bfk\b', 'fakultas kedokteran', text)
        text = re.sub(r'\bfeb\b', 'fakultas ekonomi bisnis', text)
        text = re.sub(r'\bfh\b', 'fakultas hukum', text)
        text = re.sub(r'\bfisip\b', 'fakultas ilmu sosial politik', text)
        text = re.sub(r'\bfib\b', 'fakultas ilmu budaya', text)
        text = re.sub(r'\bfpsi\b', 'fakultas psikologi', text)
        text = re.sub(r'\bfkg\b', 'fakultas kedokteran gigi', text)
        text = re.sub(r'\bfkm\b', 'fakultas kesehatan masyarakat', text)
        text = re.sub(r'\bfik\b', 'fakultas ilmu keperawatan', text)
        text = re.sub(r'\bmipa\b', 'matematika ilmu pengetahuan alam', text)
        
        # Remove special characters but keep spaces and alphanumeric
        text = re.sub(r'[^\w\s]', ' ', text)
        
        # Multiple spaces to single space
        text = re.sub(r'\s+', ' ', text).strip()
        
        # Split into words
        words = text.split()
        
        # Filter and clean words
        keywords = []
        for word in words:
            word = word.strip()
            if (len(word) >= 2 and  # Allow 2-letter words for flexibility
                word not in self.stopwords and 
                not word.isdigit() and
                re.match(r'^[a-zA-Z0-9]+$', word)):  # Allow alphanumeric
                keywords.append(word)
        
        # Add n-grams for better matching
        bigrams = []
        for i in range(len(keywords) - 1):
            bigram = f"{keywords[i]} {keywords[i+1]}"
            bigrams.append(bigram)
        
        # Combine unigrams and bigrams
        all_keywords = keywords + bigrams
        
        # Remove duplicates while preserving order
        seen = set()
        result = []
        for keyword in all_keywords:
            if keyword not in seen:
                seen.add(keyword)
                result.append(keyword)
        
        return result
    
    def calculate_tf_idf(self, term: str, document_keywords: List[str], all_documents: List[List[str]]) -> float:
        """Hitung TF-IDF score untuk term dalam dokumen"""
        if not document_keywords or not all_documents or not term:
            return 0.0
        
        try:
            # Term Frequency (TF) with normalization
            tf = document_keywords.count(term) / len(document_keywords)
            
            # Document Frequency (DF)
            df = sum(1 for doc in all_documents if term in doc)
            
            # Inverse Document Frequency (IDF)
            if df == 0:
                return 0.0
            
            idf = math.log(len(all_documents) / df) + 1  # Add 1 to avoid zero
            
            return tf * idf
        except (ZeroDivisionError, ValueError) as e:
            self.logger.warning(f"Error calculating TF-IDF for term '{term}': {e}")
            return 0.0
    
    def create_search_index(self, faculty_id: int, faculty_data: Dict) -> bool:
        """Buat search index untuk satu fakultas dengan retry mechanism"""
        for attempt in range(self.max_retries):
            try:
                with self.get_db_connection() as conn:
                    cursor = conn.cursor()
                    
                    # Begin transaction
                    cursor.execute('BEGIN IMMEDIATE')
                    
                    try:
                        # Hapus index lama untuk fakultas ini
                        cursor.execute('DELETE FROM search_index WHERE faculty_id = ?', (faculty_id,))
                        
                        # Extract keywords dari berbagai field
                        index_entries = []
                        
                        # Index nama fakultas (weight tinggi)
                        if faculty_data.get('name'):
                            keywords = self.extract_keywords(faculty_data['name'])
                            for keyword in keywords:
                                index_entries.append({
                                    'faculty_id': faculty_id,
                                    'content_type': 'name',
                                    'content': faculty_data['name'],
                                    'keyword': keyword,
                                    'weight': 5.0  # Increased weight untuk nama
                                })
                        
                        # Index deskripsi (weight medium)
                        if faculty_data.get('description'):
                            keywords = self.extract_keywords(faculty_data['description'])
                            content_preview = faculty_data['description'][:200] + '...' if len(faculty_data['description']) > 200 else faculty_data['description']
                            for keyword in keywords:
                                index_entries.append({
                                    'faculty_id': faculty_id,
                                    'content_type': 'description',
                                    'content': content_preview,
                                    'keyword': keyword,
                                    'weight': 2.0
                                })
                        
                        # Index programs (weight medium-high)
                        for program in faculty_data.get('programs', []):
                            if program:  # Check if program is not empty
                                keywords = self.extract_keywords(program)
                                for keyword in keywords:
                                    index_entries.append({
                                        'faculty_id': faculty_id,
                                        'content_type': 'program',
                                        'content': program,
                                        'keyword': keyword,
                                        'weight': 3.0  # Increased weight untuk program
                                    })
                        
                        # Index departments (weight medium)
                        for department in faculty_data.get('departments', []):
                            if department:  # Check if department is not empty
                                keywords = self.extract_keywords(department)
                                for keyword in keywords:
                                    index_entries.append({
                                        'faculty_id': faculty_id,
                                        'content_type': 'department',
                                        'content': department,
                                        'keyword': keyword,
                                        'weight': 2.5
                                    })
                        
                        # Index contact info (weight low)
                        contact = faculty_data.get('contact', {})
                        if isinstance(contact, dict) and contact.get('address'):
                            keywords = self.extract_keywords(contact['address'])
                            for keyword in keywords:
                                index_entries.append({
                                    'faculty_id': faculty_id,
                                    'content_type': 'contact',
                                    'content': contact['address'],
                                    'keyword': keyword,
                                    'weight': 1.0
                                })
                        
                        # Index faculty_type
                        if faculty_data.get('faculty_type'):
                            keywords = self.extract_keywords(faculty_data['faculty_type'])
                            for keyword in keywords:
                                index_entries.append({
                                    'faculty_id': faculty_id,
                                    'content_type': 'type',
                                    'content': faculty_data['faculty_type'],
                                    'keyword': keyword,  
                                    'weight': 2.0
                                })
                        
                        # Batch insert untuk performance
                        if index_entries:
                            cursor.executemany('''
                                INSERT INTO search_index (faculty_id, content_type, content, keywords, weight)
                                VALUES (?, ?, ?, ?, ?)
                            ''', [
                                (entry['faculty_id'], entry['content_type'], entry['content'], 
                                 entry['keyword'], entry.get('weight', 1.0))
                                for entry in index_entries
                            ])
                        
                        # Commit transaction
                        cursor.execute('COMMIT')
                        
                        self.logger.info(f"Search index created for faculty {faculty_id}: {len(index_entries)} entries")
                        return True
                        
                    except Exception as e:
                        cursor.execute('ROLLBACK')
                        raise e
                        
            except sqlite3.OperationalError as e:
                if "locked" in str(e).lower() and attempt < self.max_retries - 1:
                    self.logger.warning(f"Database locked, retrying... (attempt {attempt + 1})")
                    time.sleep(0.5 * (attempt + 1))  # Exponential backoff
                    continue
                else:
                    self.logger.error(f"Error creating search index for faculty {faculty_id}: {e}")
                    return False
            except Exception as e:
                self.logger.error(f"Error creating search index for faculty {faculty_id}: {e}")
                return False
        
        return False
    
    def rebuild_all_indexes(self) -> Dict[str, int]:
        """Rebuild semua search indexes dengan better error handling"""
        results = {'success': 0, 'failed': 0, 'total_entries': 0}
        
        try:
            with self.get_db_connection(timeout=60.0) as conn:  # Longer timeout for rebuild
                cursor = conn.cursor()
                
                # Begin transaction
                cursor.execute('BEGIN IMMEDIATE')
                
                try:
                    # Clear existing search index
                    cursor.execute('DELETE FROM search_index')
                    self.logger.info("Cleared existing search index")
                    
                    # Get all faculties
                    cursor.execute('SELECT id FROM faculties ORDER BY id')
                    faculty_ids = [row[0] for row in cursor.fetchall()]
                    
                    cursor.execute('COMMIT')
                    
                    self.logger.info(f"Found {len(faculty_ids)} faculties to index")
                    
                    # Process each faculty individually to avoid long transactions
                    for faculty_id in faculty_ids:
                        try:
                            faculty_data = self._get_complete_faculty_data(faculty_id)
                            if faculty_data and faculty_data.get('name'):  # Ensure we have basic data
                                if self.create_search_index(faculty_id, faculty_data):
                                    results['success'] += 1
                                    if results['success'] % 10 == 0:  # Progress logging
                                        self.logger.info(f"Indexed {results['success']} faculties...")
                                else:
                                    results['failed'] += 1
                            else:
                                self.logger.warning(f"No data found for faculty {faculty_id}")
                                results['failed'] += 1
                                
                        except Exception as e:
                            self.logger.error(f"Error processing faculty {faculty_id}: {e}")
                            results['failed'] += 1
                    
                    # Count total entries created
                    with self.get_db_connection() as count_conn:
                        count_cursor = count_conn.cursor()
                        count_cursor.execute('SELECT COUNT(*) FROM search_index')
                        results['total_entries'] = count_cursor.fetchone()[0]
                    
                    self.logger.info(f"Index rebuild completed: {results}")
                    return results
                    
                except Exception as e:
                    cursor.execute('ROLLBACK')
                    raise e
                    
        except Exception as e:
            self.logger.error(f"Error rebuilding search indexes: {e}")
            return results
    
    def _get_complete_faculty_data(self, faculty_id: int) -> Dict:
        """Ambil data lengkap fakultas untuk indexing dengan better error handling"""
        try:
            with self.get_db_connection() as conn:
                conn.row_factory = sqlite3.Row
                cursor = conn.cursor()
                
                # Get faculty basic data
                cursor.execute('SELECT * FROM faculties WHERE id = ?', (faculty_id,))
                faculty_row = cursor.fetchone()
                
                if not faculty_row:
                    self.logger.warning(f"Faculty {faculty_id} not found")
                    return {}
                
                faculty_data = dict(faculty_row)
                
                # Get programs
                cursor.execute('SELECT name FROM programs WHERE faculty_id = ? AND name IS NOT NULL AND name != ""', (faculty_id,))
                faculty_data['programs'] = [row['name'] for row in cursor.fetchall()]
                
                # Get departments  
                cursor.execute('SELECT name FROM departments WHERE faculty_id = ? AND name IS NOT NULL AND name != ""', (faculty_id,))
                faculty_data['departments'] = [row['name'] for row in cursor.fetchall()]
                
                # Get contact
                cursor.execute('SELECT * FROM contacts WHERE faculty_id = ?', (faculty_id,))
                contact_row = cursor.fetchone()
                faculty_data['contact'] = dict(contact_row) if contact_row else {}
                
                return faculty_data
                
        except sqlite3.Error as e:
            self.logger.error(f"Error getting faculty data for indexing faculty {faculty_id}: {e}")
            return {}
    
    def verify_search_index(self) -> Dict:
        """Verify integrity of search index"""
        try:
            with self.get_db_connection() as conn:
                cursor = conn.cursor()
                
                verification = {}
                
                # Check total entries
                cursor.execute('SELECT COUNT(*) FROM search_index')
                verification['total_entries'] = cursor.fetchone()[0]
                
                # Check faculties with no index
                cursor.execute('''
                    SELECT COUNT(*) FROM faculties f
                    WHERE NOT EXISTS (SELECT 1 FROM search_index si WHERE si.faculty_id = f.id)
                ''')
                verification['unindexed_faculties'] = cursor.fetchone()[0]
                
                # Check empty keywords
                cursor.execute('SELECT COUNT(*) FROM search_index WHERE keywords IS NULL OR keywords = ""')
                verification['empty_keywords'] = cursor.fetchone()[0]
                
                # Check content type distribution
                cursor.execute('''
                    SELECT content_type, COUNT(*) as count
                    FROM search_index
                    GROUP BY content_type
                    ORDER BY count DESC
                ''')
                verification['content_type_distribution'] = {row[0]: row[1] for row in cursor.fetchall()}
                
                return verification
                
        except sqlite3.Error as e:
            self.logger.error(f"Error verifying search index: {e}")
            return {}
    
    def get_search_statistics(self) -> Dict:
        """Dapatkan statistik search index yang lebih comprehensive"""
        try:
            with self.get_db_connection() as conn:
                cursor = conn.cursor()
                
                stats = {}
                
                # Total entries
                cursor.execute('SELECT COUNT(*) FROM search_index')
                stats['total_entries'] = cursor.fetchone()[0]
                
                # Entries by content type
                cursor.execute('''
                    SELECT content_type, COUNT(*) as count, AVG(weight) as avg_weight
                    FROM search_index 
                    GROUP BY content_type
                    ORDER BY count DESC
                ''')
                stats['by_content_type'] = {
                    row[0]: {'count': row[1], 'avg_weight': round(row[2], 2)} 
                    for row in cursor.fetchall()
                }
                
                # Most common keywords
                cursor.execute('''
                    SELECT keywords, COUNT(*) as frequency, AVG(weight) as avg_weight
                    FROM search_index 
                    WHERE keywords IS NOT NULL AND keywords != ""
                    GROUP BY keywords 
                    ORDER BY frequency DESC 
                    LIMIT 20
                ''')
                stats['top_keywords'] = [
                    {
                        'keyword': row[0], 
                        'frequency': row[1], 
                        'avg_weight': round(row[2], 2)
                    } 
                    for row in cursor.fetchall()
                ]
                
                # Faculties with most index entries
                cursor.execute('''
                    SELECT si.faculty_id, f.name, COUNT(*) as entries 
                    FROM search_index si
                    JOIN faculties f ON si.faculty_id = f.id
                    GROUP BY si.faculty_id, f.name
                    ORDER BY entries DESC 
                    LIMIT 10
                ''')
                stats['top_indexed_faculties'] = [
                    {
                        'faculty_id': row[0], 
                        'faculty_name': row[1], 
                        'entries': row[2]
                    } 
                    for row in cursor.fetchall()
                ]
                
                return stats
                
        except sqlite3.Error as e:
            self.logger.error(f"Error getting search statistics: {e}")
            return {}


# Utility functions
def test_indexer():
    """Test function untuk indexer"""
    import os
    
    db_path = "data/ui_faculty.db"
    
    if not os.path.exists(db_path):
        print("❌ Database tidak ditemukan.")
        return
    
    print("🔄 Testing Search Indexer...")
    
    indexer = SearchIndexer(db_path)
    
    # Test verification
    print("\n📊 Verifying current index...")
    verification = indexer.verify_search_index()
    print(f"Total entries: {verification.get('total_entries', 0)}")
    print(f"Unindexed faculties: {verification.get('unindexed_faculties', 0)}")
    print(f"Empty keywords: {verification.get('empty_keywords', 0)}")
    
    # Test rebuild if needed
    if verification.get('total_entries', 0) == 0 or verification.get('unindexed_faculties', 0) > 0:
        print("\n🔄 Rebuilding search index...")
        results = indexer.rebuild_all_indexes()
        print(f"Rebuild results: {results}")
    
    # Show statistics
    print("\n📈 Search Index Statistics:")
    stats = indexer.get_search_statistics()
    print(f"Total entries: {stats.get('total_entries', 0)}")
    print(f"Content types: {stats.get('by_content_type', {})}")
    
    if stats.get('top_keywords'):
        print("\nTop keywords:")
        for kw in stats['top_keywords'][:5]:
            print(f"  - {kw['keyword']}: {kw['frequency']} times")


if __name__ == "__main__":
    # Setup logging
    logging.basicConfig(level=logging.INFO)
    test_indexer()