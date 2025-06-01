from flask import Flask, render_template, request, jsonify
import os
import logging
from datetime import datetime

from config import config
from database.models import create_models
from database.database import DatabaseOperations
from crawler.bfs_crawler import NaturalUIFacultyCrawler
from search.search_engine import FacultySearchEngine

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

def create_app(config_name='default'):
    app = Flask(__name__)
    app.config.from_object(config[config_name])
    
    db_operations = DatabaseOperations(app.config['DATABASE_PATH'])
    
    try:
        search_engine = FacultySearchEngine(app.config['DATABASE_PATH'])
        app.logger.info("Search engine initialized successfully")
    except Exception as e:
        app.logger.error(f"Failed to initialize search engine: {e}")
        search_engine = None
    
    @app.route('/')
    def index():
        try:
            stats = db_operations.get_faculty_statistics()
            recent_faculties = db_operations.models['faculty'].get_all(limit=5)
            
            return render_template('index.html', 
                                 stats=stats, 
                                 recent_faculties=recent_faculties)
        except Exception as e:
            app.logger.error(f"Error in index route: {e}")
            return render_template('index.html', 
                                 stats={}, 
                                 recent_faculties=[])
    
    @app.route('/search')
    def search():
        query = request.args.get('q', '').strip()
        page = int(request.args.get('page', 1))
        per_page = app.config.get('ITEMS_PER_PAGE', 10)
        search_type = request.args.get('type', 'comprehensive')
        
        if not query:
            return render_template('search.html', 
                                 results=[], 
                                 query='', 
                                 total=0,
                                 suggestions=[])
        
        try:
            if search_engine:
                results = search_engine.search_faculties(
                    query, 
                    limit=app.config.get('SEARCH_RESULTS_LIMIT', 50),
                    search_type=search_type
                )
                suggestions = search_engine.get_search_suggestions(query, limit=5)
            else:
                results = db_operations.models['faculty'].search(
                    query, 
                    limit=app.config.get('SEARCH_RESULTS_LIMIT', 20)
                )
                suggestions = db_operations.get_search_suggestions(query, limit=5)
            
            start = (page - 1) * per_page
            end = start + per_page
            paginated_results = results[start:end]
            
            return render_template('search.html',
                                 results=paginated_results,
                                 query=query,
                                 total=len(results),
                                 page=page,
                                 per_page=per_page,
                                 suggestions=suggestions,
                                 search_type=search_type)
                                 
        except Exception as e:
            app.logger.error(f"Error in search route: {e}")
            return render_template('search.html',
                                 results=[],
                                 query=query,
                                 total=0,
                                 suggestions=[],
                                 error=f"Terjadi kesalahan dalam pencarian: {str(e)}")
    
    @app.route('/faculty/<int:faculty_id>')
    def faculty_detail(faculty_id):
        try:
            faculty = db_operations.models['faculty'].get_by_id(faculty_id)
            
            if not faculty:
                return render_template('404.html'), 404
            
            return render_template('faculty.html', faculty=faculty)
            
        except Exception as e:
            app.logger.error(f"Error in faculty detail route: {e}")
            return render_template('404.html'), 404
    
    @app.route('/api/search')
    def api_search():
        query = request.args.get('q', '').strip()
        limit = int(request.args.get('limit', 10))
        search_type = request.args.get('type', 'comprehensive')
        
        if not query:
            return jsonify({'results': [], 'total': 0})
        
        try:
            if search_engine:
                results = search_engine.search_faculties(query, limit=limit, search_type=search_type)
            else:
                results = db_operations.models['faculty'].search(query, limit=limit)
            
            api_results = []
            for faculty in results:
                api_results.append({
                    'id': faculty['id'],
                    'name': faculty['name'],
                    'url': faculty['url'],
                    'description': faculty.get('description', '')[:100] + '...' if faculty.get('description', '') else '',
                    'faculty_type': faculty.get('faculty_type', 'general'),
                    'search_score': faculty.get('search_score', 0)
                })
            
            return jsonify({
                'results': api_results,
                'total': len(api_results),
                'query': query
            })
            
        except Exception as e:
            app.logger.error(f"Error in API search: {e}")
            return jsonify({'error': 'Search failed', 'message': str(e)}), 500
    
    @app.route('/api/suggestions')
    def api_suggestions():
        query = request.args.get('q', '').strip()
        
        if not query or len(query) < 2:
            return jsonify({'suggestions': []})
        
        try:
            if search_engine:
                suggestions = search_engine.get_search_suggestions(query, limit=5)
            else:
                suggestions = db_operations.get_search_suggestions(query, limit=5)
            return jsonify({'suggestions': suggestions})
            
        except Exception as e:
            app.logger.error(f"Error getting suggestions: {e}")
            return jsonify({'suggestions': []})
    
    @app.route('/admin')
    def admin_panel():
        try:
            stats = db_operations.get_faculty_statistics()
            crawl_info = db_operations.models['crawl_metadata'].get_latest_crawl()
            
            search_debug = None
            if search_engine:
                search_debug = search_engine.debug_search("test")
            
            return render_template('admin.html', 
                                 stats=stats, 
                                 crawl_info=crawl_info,
                                 search_debug=search_debug)
        except Exception as e:
            app.logger.error(f"Error in admin panel: {e}")
            return render_template('admin.html', 
                                 stats={}, 
                                 crawl_info=None,
                                 search_debug=None)
    
    @app.route('/admin/crawl', methods=['POST'])
    def start_crawl():
        try:
            max_depth = int(request.form.get('max_depth', 4))
            max_pages = int(request.form.get('max_pages', 50))
            delay = int(request.form.get('delay', 2))
            
            crawler = NaturalUIFacultyCrawler(
                base_url="https://www.ui.ac.id/",
                delay=delay
            )
            
            start_time = datetime.now()
            faculty_data = crawler.natural_crawl_bfs(max_depth=max_depth, max_pages=max_pages)
            end_time = datetime.now()
            
            crawl_duration = int((end_time - start_time).total_seconds())
            
            import_results = db_operations.import_from_crawler(faculty_data)
            
            db_operations.models['crawl_metadata'].create_crawl_record(
                base_url="https://www.ui.ac.id/",
                total_faculties=import_results['success'],
                pages_crawled=len(crawler.visited),
                duration=crawl_duration
            )
            
            crawler.save_results(app.config['JSON_BACKUP_PATH'])
            
            if search_engine:
                try:
                    app.logger.info("Search index should be rebuilt after crawling")
                except Exception as e:
                    app.logger.error(f"Error rebuilding search index: {e}")
            
            crawler_summary = crawler.get_crawl_summary()
            
            return jsonify({
                'success': True,
                'message': 'Natural BFS crawling completed successfully!',
                'results': {
                    'faculties_found': import_results['success'],
                    'pages_crawled': len(crawler.visited),
                    'duration_seconds': crawl_duration,
                    'failed': import_results['failed'],
                    'errors': import_results['errors'][:5],
                    'navigation_stages': crawler_summary.get('navigation_stages', {}),
                    'discovery_paths': crawler_summary.get('discovery_paths', [])[:3]
                }
            })
            
        except Exception as e:
            app.logger.error(f"Error during natural BFS crawling: {e}")
            return jsonify({
                'success': False,
                'message': f'Crawling failed: {str(e)}'
            }), 500
    
    @app.route('/admin/import', methods=['POST'])
    def import_json():
        try:
            json_file = app.config['JSON_BACKUP_PATH']
            
            if not os.path.exists(json_file):
                return jsonify({
                    'success': False,
                    'message': 'JSON backup file not found'
                }), 404
            
            results = db_operations.import_from_json(json_file)
            
            return jsonify({
                'success': True,
                'message': 'Import completed successfully!',
                'results': results
            })
            
        except Exception as e:
            app.logger.error(f"Error during import: {e}")
            return jsonify({
                'success': False,
                'message': f'Import failed: {str(e)}'
            }), 500
    
    @app.route('/admin/clear', methods=['POST'])
    def clear_data():
        try:
            success = db_operations.clear_all_data()
            
            if success:
                return jsonify({
                    'success': True,
                    'message': 'All data cleared successfully!'
                })
            else:
                return jsonify({
                    'success': False,
                    'message': 'Failed to clear data'
                }), 500
                
        except Exception as e:
            app.logger.error(f"Error clearing data: {e}")
            return jsonify({
                'success': False,
                'message': f'Clear failed: {str(e)}'
            }), 500
    
    @app.route('/admin/backup', methods=['POST'])
    def backup_data():
        try:
            backup_file = f"data/backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
            success = db_operations.backup_to_json(backup_file)
            
            if success:
                return jsonify({
                    'success': True,
                    'message': f'Data backed up to {backup_file}'
                })
            else:
                return jsonify({
                    'success': False,
                    'message': 'Backup failed'
                }), 500
                
        except Exception as e:
            app.logger.error(f"Error during backup: {e}")
            return jsonify({
                'success': False,
                'message': f'Backup failed: {str(e)}'
            }), 500
    
    @app.route('/admin/test-crawl', methods=['POST'])
    def test_crawl():
        try:
            crawler = NaturalUIFacultyCrawler(
                base_url="https://www.ui.ac.id/",
                delay=1
            )
            
            start_time = datetime.now()
            faculty_data = crawler.natural_crawl_bfs(max_depth=2, max_pages=10)
            end_time = datetime.now()
            
            crawl_duration = int((end_time - start_time).total_seconds())
            crawler_summary = crawler.get_crawl_summary()
            
            return jsonify({
                'success': True,
                'message': 'Test crawl completed!',
                'results': {
                    'faculties_found': len(faculty_data),
                    'pages_crawled': len(crawler.visited),
                    'duration_seconds': crawl_duration,
                    'navigation_stages': crawler_summary.get('navigation_stages', {}),
                    'sample_faculties': [f['name'] for f in faculty_data[:3]] if faculty_data else [],
                    'discovery_paths': crawler_summary.get('discovery_paths', [])
                }
            })
            
        except Exception as e:
            app.logger.error(f"Error during test crawl: {e}")
            return jsonify({
                'success': False,
                'message': f'Test crawl failed: {str(e)}'
            }), 500
    
    @app.errorhandler(404)
    def not_found(error):
        return render_template('404.html'), 404
    
    @app.errorhandler(500)
    def internal_error(error):
        app.logger.error(f"Internal server error: {error}")
        return render_template('500.html'), 500
    
    os.makedirs('data', exist_ok=True)
    os.makedirs('data/logs', exist_ok=True)
    
    return app

def run_initial_crawl():
    try:
        from config import DevelopmentConfig
        db_ops = DatabaseOperations(DevelopmentConfig.DATABASE_PATH)
        
        faculty_count = db_ops.models['faculty'].count()
        
        if faculty_count == 0:
            print("🔍 Database kosong. Menjalankan natural BFS crawling awal...")
            
            crawler = NaturalUIFacultyCrawler(
                base_url="https://www.ui.ac.id/",
                delay=2
            )
            
            faculty_data = crawler.natural_crawl_bfs(max_depth=2, max_pages=30)
            
            results = db_ops.import_from_crawler(faculty_data)
            
            crawler_summary = crawler.get_crawl_summary()
            
            print(f"✅ Natural BFS crawling awal selesai:")
            print(f"   📊 {results['success']} fakultas ditemukan")
            print(f"   🌐 {len(crawler.visited)} halaman dikunjungi")
            print(f"   🎯 Navigation stages: {crawler_summary.get('navigation_stages', {})}")
            
            if crawler_summary.get('faculties'):
                print("   🏛️  Fakultas ditemukan:")
                for faculty in crawler_summary['faculties'][:17]:
                    print(f"      - {faculty['name']} (Stage: {faculty['discovery_stage']})")
            
        else:
            print(f"📊 Database sudah berisi {faculty_count} fakultas")
            
    except Exception as e:
        print(f"Error dalam initial natural BFS crawl: {e}")

if __name__ == '__main__':
    config_name = os.environ.get('FLASK_CONFIG', 'development')
    
    app = create_app(config_name)
    
    if config_name == 'development':
        run_initial_crawl()
    
    app.run(
        host='0.0.0.0',
        port=int(os.environ.get('PORT', 5000)),
        debug=app.config['DEBUG']
    )