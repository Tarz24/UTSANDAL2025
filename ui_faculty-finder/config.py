import os

class Config:
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'ui-faculty-finder-secret-key-2024'
    
    DATABASE_PATH = os.path.join(os.path.dirname(__file__), 'data', 'ui_faculty.db')
    JSON_BACKUP_PATH = os.path.join(os.path.dirname(__file__), 'data', 'faculty_data.json')
    
    BASE_URL = 'https://www.ui.ac.id/'
    CRAWLER_DELAY = 1
    MAX_CRAWL_DEPTH = 6
    MAX_CRAWL_PAGES = 300
    
    SEARCH_RESULTS_LIMIT = 20
    MIN_SIMILARITY_SCORE = 0.1
    
    LOG_LEVEL = 'INFO'
    LOG_FILE = os.path.join(os.path.dirname(__file__), 'data', 'logs', 'app.log')
    
    ITEMS_PER_PAGE = 10
    
    @staticmethod
    def init_app(app):
        pass

class DevelopmentConfig(Config):
    DEBUG = True
    CRAWLER_DELAY = 2

class ProductionConfig(Config):
    DEBUG = False
    CRAWLER_DELAY = 3

class TestingConfig(Config):
    TESTING = True
    DATABASE_PATH = ':memory:'
    MAX_CRAWL_PAGES = 5

config = {
    'development': DevelopmentConfig,
    'production': ProductionConfig,
    'testing': TestingConfig,
    'default': DevelopmentConfig
}