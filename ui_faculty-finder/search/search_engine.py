import re
import sqlite3
import logging
from typing import Dict, List, Optional, Tuple
from collections import defaultdict
import math
import os

class FacultySearchEngine:
    """
    Search engine untuk mencari fakultas UI dengan berbagai metode pencarian
    """
    
    def __init__(self, db_path: str):
        self.db_path = db_path
        self.logger = logging.getLogger(__name__)
        
        # Check if database exists
        if not os.path.exists(db_path):
            self.logger.error(f"Database not found: {db_path}")
            raise FileNotFoundError(f"Database not found: {db_path}")
        
        # Stopwords bahasa Indonesia
        self.stopwords = {
            'dan', 'atau', 'yang', 'dari', 'di', 'ke', 'pada', 'untuk', 'dengan', 
            'adalah', 'ini', 'itu', 'akan', 'ada', 'dapat', 'hanya', 'juga',
            'tidak', 'sudah', 'telah', 'bisa', 'saya', 'kami', 'kita', 'mereka'
        }
        
        # Synonym mapping untuk memperbaiki pencarian
        self.synonyms = {
            'kedokteran': ['medical', 'medicine', 'dokter', 'medis'],
            'teknik': ['engineering', 'engineer', 'teknologi', 'tech'],
            'ekonomi': ['economy', 'business', 'bisnis', 'manajemen'],
            'hukum': ['law', 'legal'],
            'ilmu': ['science', 'sains'],
            'komputer': ['computer', 'informatika', 'it'],
            'sosial': ['social'],
            'budaya': ['culture', 'cultural'],
            'politik': ['political', 'politics'],
            'matematika': ['math', 'mathematics'],
            'psikologi': ['psychology', 'psych'],
            'kesehatan': ['health'],
            'gigi': ['dental', 'dentistry'],
            'keperawatan': ['nursing'],
            'vokasi': ['vocational']
        }
        
        # Initialize database and verify tables
        self._verify_database_structure()
    
    def _verify_database_structure(self):
        """Verify database structure and create missing tables/indexes if needed"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                # Check if search_index table exists
                cursor.execute("""
                    SELECT name FROM sqlite_master 
                    WHERE type='table' AND name='search_index'
                """)
                
                if not cursor.fetchone():
                    self.logger.warning("search_index table not found, creating basic structure")
                    # Create basic search_index table if it doesn't exist
                    cursor.execute("""
                        CREATE TABLE IF NOT EXISTS search_index (
                            id INTEGER PRIMARY KEY AUTOINCREMENT,
                            faculty_id INTEGER NOT NULL,
                            content_type TEXT NOT NULL,
                            content TEXT,
                            keywords TEXT,
                            weight REAL DEFAULT 1.0,
                            FOREIGN KEY (faculty_id) REFERENCES faculties (id)
                        )
                    """)
                    
                    # Create indexes
                    cursor.execute("CREATE INDEX IF NOT EXISTS idx_search_faculty_id ON search_index(faculty_id)")
                    cursor.execute("CREATE INDEX IF NOT EXISTS idx_search_keywords ON search_index(keywords)")
                    
                    conn.commit()
                    self.logger.info("Created search_index table structure")
                
        except sqlite3.Error as e:
            self.logger.error(f"Error verifying database structure: {e}")
    
    def preprocess_query(self, query: str) -> List[str]:
        """Preprocessing query pencarian"""
        if not query:
            return []
        
        # Convert to lowercase
        query = query.lower().strip()
        
        # Remove special characters and extra spaces
        query = re.sub(r'[^\w\s]', ' ', query)
        query = re.sub(r'\s+', ' ', query)
        
        # Split into words
        words = query.split()
        
        # Remove stopwords and short words
        words = [word for word in words if word not in self.stopwords and len(word) > 2]
        
        # Add synonyms
        expanded_words = words.copy()
        for word in words:
            if word in self.synonyms:
                expanded_words.extend(self.synonyms[word])
        
        return list(set(expanded_words))  # Remove duplicates
    
    def search_faculties(self, query: str, limit: int = 20, search_type: str = 'comprehensive') -> List[Dict]:
        """
        Main search method dengan berbagai strategi pencarian
        """
        if not query or not query.strip():
            self.logger.warning("Empty query provided")
            return []
        
        processed_words = self.preprocess_query(query)
        if not processed_words:
            self.logger.warning(f"No valid words found in query: {query}")
            return []
        
        self.logger.info(f"Searching for: {query} -> {processed_words}")
        
        try:
            with sqlite3.connect(self.db_path, timeout=30.0) as conn:  # Add timeout
                conn.row_factory = sqlite3.Row
                
                # First try to check if search_index has data
                cursor = conn.cursor()
                cursor.execute("SELECT COUNT(*) FROM search_index")
                index_count = cursor.fetchone()[0]
                
                if index_count == 0:
                    self.logger.warning("Search index is empty, falling back to direct search")
                    return self._fallback_search(conn, processed_words, limit)
                
                if search_type == 'comprehensive':
                    results = self._comprehensive_search(conn, processed_words, limit)
                elif search_type == 'name':
                    results = self._search_by_name(conn, processed_words, limit)
                elif search_type == 'description':
                    results = self._search_by_description(conn, processed_words, limit)
                elif search_type == 'program':
                    results = self._search_by_program(conn, processed_words, limit)
                else:
                    results = self._comprehensive_search(conn, processed_words, limit)
                
                self.logger.info(f"Found {len(results)} results")
                
                # Enrich results with additional data
                return self._enrich_search_results(conn, results)
        
        except sqlite3.Error as e:
            self.logger.error(f"Database error searching faculties: {e}")
            return []
        except Exception as e:
            self.logger.error(f"Unexpected error searching faculties: {e}")
            return []
    
    def _fallback_search(self, conn, words: List[str], limit: int) -> List[Tuple]:
        """Fallback search when search_index is empty"""
        cursor = conn.cursor()
        
        word_conditions = []
        params = []
        
        for word in words:
            word_pattern = f"%{word}%"
            word_conditions.append("""
                (f.name LIKE ? OR f.description LIKE ?)
            """)
            params.extend([word_pattern, word_pattern])
        
        if not word_conditions:
            return []
        
        search_condition = " OR ".join(word_conditions)
        
        query = f"""
            SELECT f.*, 50 as final_score
            FROM faculties f
            WHERE ({search_condition})
            ORDER BY f.name ASC
            LIMIT ?
        """
        
        params.append(limit)
        cursor.execute(query, params)
        return cursor.fetchall()
    
    def _comprehensive_search(self, conn, words: List[str], limit: int) -> List[Tuple]:
        """Pencarian komprehensif dengan scoring - simplified version"""
        cursor = conn.cursor()
        
        # Simplified search with better error handling
        word_conditions = []
        search_params = []
        
        for word in words:
            word_pattern = f"%{word}%"
            word_conditions.append("""
                (si.keywords LIKE ? OR si.content LIKE ? OR f.name LIKE ?)
            """)
            search_params.extend([word_pattern, word_pattern, word_pattern])
        
        if not word_conditions:
            return []
        
        search_condition = " OR ".join(word_conditions)
        
        # Simplified scoring query
        query = f"""
            SELECT DISTINCT 
                f.id,
                f.name,
                f.url,
                f.description,
                f.faculty_type,
                f.created_at,
                COUNT(DISTINCT si.id) as match_count,
                -- Simple scoring based on content type
                SUM(CASE 
                    WHEN si.content_type = 'name' THEN 100
                    WHEN si.content_type = 'program' THEN 70
                    WHEN si.content_type = 'description' THEN 60
                    WHEN si.content_type = 'department' THEN 50
                    ELSE 10
                END) as final_score
            FROM faculties f
            LEFT JOIN search_index si ON f.id = si.faculty_id
            WHERE ({search_condition})
            GROUP BY f.id, f.name, f.url, f.description, f.faculty_type, f.created_at
            ORDER BY final_score DESC, f.name ASC
            LIMIT ?
        """
        
        search_params.append(limit)
        
        try:
            cursor.execute(query, search_params)
            return cursor.fetchall()
        except sqlite3.Error as e:
            self.logger.error(f"Error in comprehensive search: {e}")
            # Fallback to simple search
            return self._fallback_search(conn, words, limit)
    
    def _search_by_name(self, conn, words: List[str], limit: int) -> List[Tuple]:
        """Pencarian berdasarkan nama fakultas"""
        cursor = conn.cursor()
        
        word_conditions = []
        params = []
        
        for word in words:
            word_conditions.append("LOWER(f.name) LIKE LOWER(?)")
            params.append(f"%{word}%")
        
        if not word_conditions:
            return []
        
        condition = " AND ".join(word_conditions)
        
        query = f"""
            SELECT f.*, 100 as final_score
            FROM faculties f
            WHERE {condition}
            ORDER BY LENGTH(f.name) ASC, f.name ASC
            LIMIT ?
        """
        
        params.append(limit)
        cursor.execute(query, params)
        return cursor.fetchall()
    
    def _search_by_description(self, conn, words: List[str], limit: int) -> List[Tuple]:
        """Pencarian berdasarkan deskripsi"""
        cursor = conn.cursor()
        
        word_conditions = []
        params = []
        
        for word in words:
            word_conditions.append("LOWER(f.description) LIKE LOWER(?)")
            params.append(f"%{word}%")
        
        if not word_conditions:
            return []
        
        condition = " OR ".join(word_conditions)
        
        query = f"""
            SELECT f.*, 75 as final_score
            FROM faculties f
            WHERE f.description IS NOT NULL AND f.description != '' AND ({condition})
            ORDER BY LENGTH(f.description) ASC, f.name ASC
            LIMIT ?
        """
        
        params.append(limit)
        cursor.execute(query, params)
        return cursor.fetchall()
    
    def _search_by_program(self, conn, words: List[str], limit: int) -> List[Tuple]:
        """Pencarian berdasarkan program studi"""
        cursor = conn.cursor()
        
        word_conditions = []
        params = []
        
        for word in words:
            word_conditions.append("LOWER(p.name) LIKE LOWER(?)")
            params.append(f"%{word}%")
        
        if not word_conditions:
            return []
        
        condition = " OR ".join(word_conditions)
        
        query = f"""
            SELECT DISTINCT f.*, 85 as final_score
            FROM faculties f
            JOIN programs p ON f.id = p.faculty_id
            WHERE {condition}
            ORDER BY f.name ASC
            LIMIT ?
        """
        
        params.append(limit)
        cursor.execute(query, params)
        return cursor.fetchall()
    
    def _enrich_search_results(self, conn, results: List[Tuple]) -> List[Dict]:
        """Enrich hasil pencarian dengan data tambahan"""
        enriched_results = []
        cursor = conn.cursor()
        
        for result in results:
            try:
                faculty_dict = dict(result)
                faculty_id = faculty_dict['id']
                
                # Get programs
                cursor.execute('SELECT name FROM programs WHERE faculty_id = ?', (faculty_id,))
                programs = [row[0] for row in cursor.fetchall()]
                faculty_dict['programs'] = programs
                faculty_dict['programs_count'] = len(programs)
                
                # Get departments
                cursor.execute('SELECT name FROM departments WHERE faculty_id = ?', (faculty_id,))
                departments = [row[0] for row in cursor.fetchall()]
                faculty_dict['departments'] = departments
                faculty_dict['departments_count'] = len(departments)
                
                # Get contact info
                cursor.execute('SELECT * FROM contacts WHERE faculty_id = ?', (faculty_id,))
                contact_row = cursor.fetchone()
                faculty_dict['contact'] = dict(contact_row) if contact_row else {}
                
                # Get route (with error handling)
                try:
                    cursor.execute('''
                        SELECT name, url FROM routes WHERE faculty_id = ? ORDER BY step_order
                    ''', (faculty_id,))
                    routes = [{'name': row[0], 'url': row[1]} for row in cursor.fetchall()]
                    faculty_dict['route'] = routes
                except sqlite3.Error:
                    faculty_dict['route'] = []
                
                # Add search relevance info
                faculty_dict['search_score'] = faculty_dict.get('final_score', 0)
                
                enriched_results.append(faculty_dict)
                
            except Exception as e:
                self.logger.error(f"Error enriching result for faculty {result.get('id', 'unknown')}: {e}")
                continue
        
        return enriched_results
    
    def get_search_suggestions(self, query: str, limit: int = 5) -> List[str]:
        """Dapatkan saran pencarian berdasarkan query parsial"""
        if not query or len(query) < 2:
            return []
        
        try:
            with sqlite3.connect(self.db_path, timeout=10.0) as conn:
                cursor = conn.cursor()
                
                search_pattern = f"%{query.lower()}%"
                suggestions = set()
                
                # From faculty names
                cursor.execute('''
                    SELECT DISTINCT name FROM faculties 
                    WHERE LOWER(name) LIKE ? 
                    ORDER BY LENGTH(name) ASC
                    LIMIT ?
                ''', (search_pattern, limit))
                
                for row in cursor.fetchall():
                    suggestions.add(row[0])
                
                # From programs (if table exists)
                try:
                    cursor.execute('''
                        SELECT DISTINCT name FROM programs 
                        WHERE LOWER(name) LIKE ? 
                        ORDER BY LENGTH(name) ASC
                        LIMIT ?
                    ''', (search_pattern, limit))
                    
                    for row in cursor.fetchall():
                        suggestions.add(row[0])
                except sqlite3.Error:
                    pass  # Table might not exist
                
                return list(suggestions)[:limit]
        
        except sqlite3.Error as e:
            self.logger.error(f"Error getting search suggestions: {e}")
            return []
    
    def get_faculty_by_type(self, faculty_type: str, limit: int = 20) -> List[Dict]:
        """Dapatkan fakultas berdasarkan tipe"""
        try:
            with sqlite3.connect(self.db_path, timeout=10.0) as conn:
                conn.row_factory = sqlite3.Row
                cursor = conn.cursor()
                
                cursor.execute('''
                    SELECT * FROM faculties 
                    WHERE faculty_type = ? 
                    ORDER BY name ASC 
                    LIMIT ?
                ''', (faculty_type, limit))
                
                results = cursor.fetchall()
                return self._enrich_search_results(conn, results)
        
        except sqlite3.Error as e:
            self.logger.error(f"Error getting faculties by type: {e}")
            return []
    
    def debug_search(self, query: str) -> Dict:
        """Debug function untuk troubleshooting search issues"""
        debug_info = {
            'query': query,
            'processed_words': [],
            'database_exists': False,
            'faculties_count': 0,
            'search_index_count': 0,
            'tables': [],
            'sample_faculties': [],
            'error': None
        }
        
        try:
            debug_info['database_exists'] = os.path.exists(self.db_path)
            debug_info['processed_words'] = self.preprocess_query(query)
            
            with sqlite3.connect(self.db_path, timeout=10.0) as conn:
                conn.row_factory = sqlite3.Row
                cursor = conn.cursor()
                
                # Get all tables
                cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
                debug_info['tables'] = [row[0] for row in cursor.fetchall()]
                
                # Count faculties
                if 'faculties' in debug_info['tables']:
                    cursor.execute("SELECT COUNT(*) FROM faculties")
                    debug_info['faculties_count'] = cursor.fetchone()[0]
                    
                    # Get sample faculties
                    cursor.execute("SELECT id, name FROM faculties LIMIT 5")
                    debug_info['sample_faculties'] = [dict(row) for row in cursor.fetchall()]
                
                # Count search index
                if 'search_index' in debug_info['tables']:
                    cursor.execute("SELECT COUNT(*) FROM search_index")
                    debug_info['search_index_count'] = cursor.fetchone()[0]
                
        except Exception as e:
            debug_info['error'] = str(e)
        
        return debug_info


# Helper function
def create_search_engine(db_path: str) -> FacultySearchEngine:
    """Factory function untuk membuat search engine"""
    return FacultySearchEngine(db_path)


# Test function dengan better error handling
def test_search_engine():
    """Test function untuk search engine dengan debugging"""
    import logging
    
    # Setup logging
    logging.basicConfig(level=logging.INFO)
    
    db_path = "data/ui_faculty.db"
    
    print("🔍 Testing Faculty Search Engine...")
    
    try:
        search_engine = FacultySearchEngine(db_path)
        
        # Debug info first
        debug_info = search_engine.debug_search("teknik")
        print(f"\n📊 Debug Info:")
        print(f"  Database exists: {debug_info['database_exists']}")
        print(f"  Tables: {debug_info['tables']}")
        print(f"  Faculties count: {debug_info['faculties_count']}")
        print(f"  Search index count: {debug_info['search_index_count']}")
        print(f"  Sample faculties: {debug_info['sample_faculties']}")
        if debug_info['error']:
            print(f"  Error: {debug_info['error']}")
        
        # Test queries
        test_queries = [
            "teknik",
            "kedokteran", 
            "ekonomi",
            "ilmu komputer"
        ]
        
        for query in test_queries:
            print(f"\n🔎 Searching for: '{query}'")
            results = search_engine.search_faculties(query, limit=3)
            
            if results:
                for i, result in enumerate(results, 1):
                    print(f"  {i}. {result['name']} (Score: {result.get('search_score', 0)})")
                    print(f"     Programs: {result['programs_count']}, URL: {result.get('url', 'N/A')}")
            else:
                print("  ❌ No results found.")
        
    except Exception as e:
        print(f"❌ Error creating search engine: {e}")
        return


if __name__ == "__main__":
    test_search_engine()