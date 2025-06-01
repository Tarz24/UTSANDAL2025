import json
import sqlite3
import logging
from typing import Dict, List, Optional
from .models import create_models

class DatabaseOperations:
    """Helper class untuk operasi database yang lebih kompleks"""
    
    def __init__(self, db_path: str):
        self.db_path = db_path
        self.models = create_models(db_path)
        self.logger = logging.getLogger(__name__)
    
    def import_from_crawler(self, crawler_data: List[Dict]) -> Dict:
        """Import data dari hasil crawler ke database"""
        results = {
            'success': 0,
            'failed': 0,
            'errors': []
        }
        
        try:
            for faculty_data in crawler_data:
                try:
                    faculty_id = self.models['faculty'].create(faculty_data)
                    if faculty_id:
                        results['success'] += 1
                    else:
                        results['failed'] += 1
                        results['errors'].append(f"Failed to create faculty: {faculty_data.get('name', 'Unknown')}")
                        
                except Exception as e:
                    results['failed'] += 1
                    results['errors'].append(f"Error processing {faculty_data.get('name', 'Unknown')}: {str(e)}")
            
            self.models['crawl_metadata'].create_crawl_record(
                base_url="https://www.ui.ac.id/",
                total_faculties=results['success'],
                pages_crawled=len(crawler_data)
            )
            
            self.logger.info(f"Import completed: {results['success']} success, {results['failed']} failed")
            return results
            
        except Exception as e:
            self.logger.error(f"Error importing crawler data: {e}")
            results['errors'].append(str(e))
            return results
    
    def import_from_json(self, json_file_path: str) -> Dict:
        """Import data dari file JSON hasil crawler"""
        try:
            with open(json_file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            faculties = data.get('faculties', [])
            return self.import_from_crawler(faculties)
            
        except FileNotFoundError:
            error_msg = f"JSON file not found: {json_file_path}"
            self.logger.error(error_msg)
            return {'success': 0, 'failed': 0, 'errors': [error_msg]}
        
        except json.JSONDecodeError as e:
            error_msg = f"Invalid JSON format: {e}"
            self.logger.error(error_msg)
            return {'success': 0, 'failed': 0, 'errors': [error_msg]}
    
    def get_search_suggestions(self, query: str, limit: int = 5) -> List[str]:
        """Dapatkan saran pencarian berdasarkan query"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                search_query = f"%{query.lower()}%"
                cursor.execute('''
                    SELECT DISTINCT content
                    FROM search_index
                    WHERE keywords LIKE ? OR content LIKE ?
                    ORDER BY LENGTH(content) ASC
                    LIMIT ?
                ''', (search_query, search_query, limit))
                
                return [row[0] for row in cursor.fetchall()]
                
        except sqlite3.Error as e:
            self.logger.error(f"Error getting search suggestions: {e}")
            return []
    
    def get_faculty_statistics(self) -> Dict:
        """Dapatkan statistik fakultas"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                cursor.execute('SELECT COUNT(*) FROM faculties')
                total_faculties = cursor.fetchone()[0]
                
                cursor.execute('''
                    SELECT faculty_type, COUNT(*) as count
                    FROM faculties
                    GROUP BY faculty_type
                ''')
                by_type = {row[0]: row[1] for row in cursor.fetchall()}
                
                cursor.execute('SELECT COUNT(*) FROM programs')
                total_programs = cursor.fetchone()[0]
                
                cursor.execute('SELECT COUNT(*) FROM departments')
                total_departments = cursor.fetchone()[0]
                
                cursor.execute('SELECT COUNT(*) FROM contacts WHERE email IS NOT NULL OR phone IS NOT NULL')
                with_contact = cursor.fetchone()[0]
                
                return {
                    'total_faculties': total_faculties,
                    'total_programs': total_programs,
                    'total_departments': total_departments,
                    'faculties_with_contact': with_contact,
                    'by_type': by_type
                }
                
        except sqlite3.Error as e:
            self.logger.error(f"Error getting statistics: {e}")
            return {}
    
    def clear_all_data(self) -> bool:
        """Hapus semua data (untuk testing atau reset)"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                tables = ['search_index', 'routes', 'contacts', 'departments', 'programs', 'faculties', 'crawl_metadata']
                
                for table in tables:
                    cursor.execute(f'DELETE FROM {table}')
                
                conn.commit()
                self.logger.info("All data cleared successfully")
                return True
                
        except sqlite3.Error as e:
            self.logger.error(f"Error clearing data: {e}")
            return False
    
    def backup_to_json(self, output_file: str) -> bool:
        """Backup data ke file JSON"""
        try:
            faculties = []
            all_faculties = self.models['faculty'].get_all()
            
            for faculty in all_faculties:
                complete_faculty = self.models['faculty'].get_by_id(faculty['id'])
                if complete_faculty:
                    faculties.append(complete_faculty)
            
            crawl_info = self.models['crawl_metadata'].get_latest_crawl()
            statistics = self.get_faculty_statistics()
            
            backup_data = {
                'backup_info': {
                    'timestamp': crawl_info.get('timestamp') if crawl_info else None,
                    'total_faculties': len(faculties),
                    'statistics': statistics
                },
                'faculties': faculties
            }
            
            with open(output_file, 'w', encoding='utf-8') as f:
                json.dump(backup_data, f, ensure_ascii=False, indent=2)
            
            self.logger.info(f"Data backed up to {output_file}")
            return True
            
        except Exception as e:
            self.logger.error(f"Error backing up data: {e}")
            return False