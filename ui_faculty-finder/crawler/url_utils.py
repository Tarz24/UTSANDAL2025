# url_utils.py
import re
from urllib.parse import urljoin, urlparse, parse_qs
from typing import Dict, List, Optional, Tuple, Set

class BFSURLUtils:
    """
    Utility class for natural BFS crawling.
    Supports natural navigation: Homepage -> Akademik -> Fakultas -> Detail
    """
    
    NAVIGATION_STAGES = {
        'homepage': {
            'priority_keywords': ['akademik', 'academic'],
            'target_stage': 'akademik',
            'description': 'Starting point - UI homepage'
        },
        'akademik': {
            'priority_keywords': ['fakultas', 'faculty'],
            'target_stage': 'fakultas_list', 
            'description': 'Academic section - looking for faculty listings'
        },
        'fakultas_list': {
            'priority_keywords': ['kedokteran', 'teknik', 'hukum', 'ekonomi', 'psikologi', 
                                'matematika', 'mipa', 'sosial', 'politik', 'budaya',
                                'keperawatan', 'kesehatan', 'komputer', 'vokasi'],
            'target_stage': 'specific_faculty',
            'description': 'Faculty listing - looking for individual faculties'
        },
        'specific_faculty': {
            'priority_keywords': ['program', 'departemen', 'tentang', 'profil'],
            'target_stage': 'faculty_detail',
            'description': 'Individual faculty page'
        }
    }
    
    @staticmethod
    def detect_navigation_stage(url: str) -> str:
        """Detect navigation stage from URL."""
        url_lower = url.lower()
        
        if url_lower in ['https://www.ui.ac.id/', 'https://ui.ac.id/']:
            return 'homepage'
        elif 'akademik' in url_lower and 'fakultas' not in url_lower:
            return 'akademik'
        elif 'akademik/fakultas' in url_lower and not any(faculty in url_lower for faculty in 
            ['kedokteran', 'teknik', 'hukum', 'ekonomi', 'psikologi']): # Basic check for specific faculty in URL
            return 'fakultas_list'
        elif any(indicator in url_lower for indicator in ['fakultas', 'faculty']): # General check
            return 'specific_faculty'
        else:
            return 'other'
    
    @staticmethod
    def is_valid_bfs_url(url: str) -> bool:
        """Validate URL for natural BFS crawling."""
        try:
            parsed = urlparse(url)
            
            if parsed.netloc not in ['www.ui.ac.id', 'ui.ac.id']: # Must be UI domain
                return False
            
            if parsed.scheme != 'https': # Must use HTTPS
                return False
            
            skip_extensions = ['.pdf', '.doc', '.docx', '.xls', '.xlsx', '.ppt', '.pptx',
                             '.jpg', '.jpeg', '.png', '.gif', '.svg', '.webp',
                             '.zip', '.rar', '.7z', '.tar', '.gz',
                             '.mp3', '.mp4', '.avi', '.mov', '.wmv']
            if any(url.lower().endswith(ext) for ext in skip_extensions): # Skip file downloads
                return False
            
            if len(url) > 200: # Skip URLs that are too long
                return False
            
            if len(parse_qs(parsed.query)) > 3: # Skip URLs with too many parameters
                return False
            
            skip_paths = ['/admin', '/login', '/search', '/ajax', '/api', '/rss', '/feed']
            if any(skip_path in url.lower() for skip_path in skip_paths): # Skip common non-content paths
                return False
            
            return True
        except:
            return False
    
    @staticmethod
    def calculate_bfs_priority(url: str, link_text: str, current_stage: str, soup=None) -> int:
        """
        Calculate URL priority for BFS based on the current navigation stage.
        Higher priority means it will be visited sooner in the BFS queue.
        """
        priority = 0
        url_lower = url.lower()
        text_lower = link_text.lower().strip()
        
        stage_info = BFSURLUtils.NAVIGATION_STAGES.get(current_stage, {})
        
        # Stage-specific priority scoring
        if current_stage == 'homepage':
            if any(keyword in text_lower for keyword in ['akademik', 'academic']): priority += 50
            elif any(keyword in url_lower for keyword in ['akademik', 'academic']): priority += 45
            if any(nav_word in text_lower for nav_word in ['menu', 'navigation', 'nav']): priority += 10
        
        elif current_stage == 'akademik':
            if any(keyword in text_lower for keyword in ['fakultas', 'faculty']): priority += 50
            elif any(keyword in url_lower for keyword in ['fakultas', 'faculty']): priority += 45
            if 'fakultas-fakultas' in text_lower or 'faculties' in text_lower: priority += 10 # Bonus for plural
        
        elif current_stage == 'fakultas_list':
            faculty_names = [
                'kedokteran', 'teknik', 'hukum', 'ekonomi', 'psikologi', 'matematika', 'mipa', 
                'ilmu pengetahuan alam', 'sosial', 'politik', 'budaya', 'ilmu budaya', 
                'keperawatan', 'kesehatan', 'komputer', 'vokasi', 'kedokteran gigi', 'farmasi'
            ]
            if any(faculty_name in text_lower for faculty_name in faculty_names): priority += 50
            elif 'fakultas' in text_lower and len(text_lower) > 8: priority += 30
        
        elif current_stage == 'specific_faculty':
            detail_keywords = ['tentang', 'about', 'profil', 'profile', 'sejarah', 'visi', 'misi',
                              'program', 'departemen', 'department', 'struktur']
            if any(keyword in text_lower for keyword in detail_keywords): priority += 40
        
        # General priority modifiers
        academic_terms = ['fakultas', 'faculty', 'akademik', 'academic', 'program studi', 'jurusan']
        if any(term in text_lower for term in academic_terms): priority += 15
        
        if soup: # Boost for important navigation elements
            link_element = soup.find('a', string=re.compile(re.escape(link_text), re.I))
            if link_element:
                if link_element.find_parent(['nav', 'header', 'menu']): priority += 10
                parent_classes = str(link_element.find_parent().get('class', [])).lower()
                if any(nav_class in parent_classes for nav_class in ['menu', 'nav', 'navigation']): priority += 8
        
        if 5 < len(text_lower) < 50: priority += 5 # Good length for navigation text
        elif len(text_lower) > 100: priority -= 5 # Too long
        
        url_depth = url.count('/') - 3  # Subtract base URL depth ('https://www.ui.ac.id/')
        if url_depth > 3: priority -= url_depth * 2 # URL depth penalty
        
        low_value_keywords = ['berita', 'news', 'artikel', 'pengumuman', 'agenda', 'gallery', 
                             'foto', 'video', 'download', 'kontak', 'contact', 'login', 'sitemap']
        if any(keyword in text_lower for keyword in low_value_keywords): priority -= 10
        
        exact_flow_matches = { # Bonus for exact matches to expected navigation flow
            'homepage': ['akademik'], 'akademik': ['fakultas', 'daftar fakultas'],
            'fakultas_list': ['fakultas kedokteran', 'fakultas teknik', 'fakultas hukum'],
            'specific_faculty': ['tentang fakultas', 'profil fakultas']
        }
        if any(match in text_lower for match in exact_flow_matches.get(current_stage, [])): priority += 20
        
        return max(0, priority)
    
    @staticmethod
    def get_bfs_navigation_links(soup, current_url: str, current_stage: str) -> List[Tuple[str, int, str]]:
        """
        Get links for BFS with priority based on navigation stage.
        Returns: List of (url, priority, link_text) tuples, sorted by priority.
        """
        links = []
        if not soup: return links
        
        for link in soup.find_all('a', href=True):
            href = link.get('href', '').strip()
            if not href: continue
            
            full_url = urljoin(current_url, href)
            if not BFSURLUtils.is_valid_bfs_url(full_url): continue # Validate URL
            
            link_text = link.get_text().strip()
            if not link_text or len(link_text) > 150: continue # Validate link text
            
            priority = BFSURLUtils.calculate_bfs_priority(full_url, link_text, current_stage, soup)
            if priority > 0: # Only add links with positive priority
                links.append((full_url, priority, link_text))
        
        links.sort(key=lambda x: x[1], reverse=True) # Sort by priority
        return links
    
    @staticmethod
    def is_faculty_content_page(url: str, soup=None, page_text: str = '') -> bool:
        """Detect if the page contains faculty content."""
        url_lower = url.lower()
        faculty_url_indicators = [
            '/fakultas/', '/faculty/', 'fakultas.', 'fk.ui.ac.id', 'ft.ui.ac.id', 'fib.ui.ac.id', 
            'fisip.ui.ac.id', 'fh.ui.ac.id', 'feb.ui.ac.id', 'fmipa.ui.ac.id', 'fpsi.ui.ac.id', 
            'fkm.ui.ac.id', 'fkg.ui.ac.id', 'fik.ui.ac.id', 'fasilkom.ui.ac.id', 'fvok.ui.ac.id'
        ]
        url_match = any(indicator in url_lower for indicator in faculty_url_indicators)
        
        content_match = False
        if page_text: # Content-based detection
            content_lower = page_text.lower()
            faculty_content_indicators = [
                'dekan', 'dean', 'fakultas', 'faculty', 'program studi', 'jurusan',
                'departemen', 'department', 'dosen', 'mahasiswa', 'sarjana', 'magister'
            ]
            content_matches = sum(1 for ind in faculty_content_indicators if ind in content_lower)
            content_match = content_matches >= 3 # Require multiple indicators
            
        return url_match or content_match
    
    @staticmethod
    def generate_bfs_breadcrumb(url: str, stage: str) -> List[Dict[str, str]]:
        """Generate breadcrumb for BFS navigation tracking."""
        breadcrumb = [{'name': 'Beranda UI', 'url': 'https://www.ui.ac.id/', 'stage': 'homepage'}]
        
        if stage in ['akademik', 'fakultas_list', 'specific_faculty']:
            breadcrumb.append({'name': 'Akademik', 'url': 'https://www.ui.ac.id/akademik/', 'stage': 'akademik'})
        
        if stage in ['fakultas_list', 'specific_faculty']:
            breadcrumb.append({'name': 'Fakultas', 'url': 'https://www.ui.ac.id/akademik/fakultas/', 'stage': 'fakultas_list'})
        
        if url not in [item['url'] for item in breadcrumb]: # Add current page if not already there
            page_name = BFSURLUtils.extract_page_name_from_url(url)
            breadcrumb.append({'name': page_name, 'url': url, 'stage': stage})
            
        return breadcrumb
    
    @staticmethod
    def extract_page_name_from_url(url: str) -> str:
        """Extract a readable page name from URL."""
        try:
            parsed = urlparse(url)
            path_parts = [part for part in parsed.path.split('/') if part]
            
            if path_parts:
                last_part = path_parts[-1]
                name_mappings = { # Common patterns to readable names
                    'fakultas': 'Fakultas', 'akademik': 'Akademik', 'kedokteran': 'Fakultas Kedokteran',
                    'teknik': 'Fakultas Teknik', 'hukum': 'Fakultas Hukum', 'ekonomi': 'Fakultas Ekonomi',
                    'psikologi': 'Fakultas Psikologi'
                }
                return name_mappings.get(last_part.lower(), 
                                       last_part.replace('-', ' ').replace('_', ' ').title())
            return 'Halaman UI'
        except:
            return 'Halaman UI'
    
    @staticmethod
    def get_bfs_starting_urls() -> List[Tuple[str, str]]:
        """Get starting URLs for natural BFS crawling."""
        return [('https://www.ui.ac.id/', 'homepage')]
    
    @staticmethod
    def validate_bfs_queue_item(url: str, depth: int, stage: str, visited: Set[str]) -> bool:
        """Validate an item for the BFS queue."""
        if url in visited: return False
        if not BFSURLUtils.is_valid_bfs_url(url): return False
        if depth > 5: return False # Depth limit for natural navigation
        if stage not in BFSURLUtils.NAVIGATION_STAGES and stage != 'other': return False # Stage validity
        return True
    
    @staticmethod
    def get_expected_navigation_flow() -> Dict[str, List[str]]:
        """Get the expected flow for natural BFS navigation."""
        return {
            'homepage': ['akademik'],
            'akademik': ['fakultas_list'],
            'fakultas_list': ['specific_faculty'],
            'specific_faculty': ['faculty_detail'] # 'faculty_detail' might be an end-state or further crawl
        }
    
    @staticmethod
    def normalize_url_for_bfs(url: str) -> str:
        """Normalize URL for BFS consistency."""
        if not url: return ""
        url = url.rstrip('/') # Remove trailing slash
        if url.startswith('http://'): url = url.replace('http://', 'https://', 1) # Ensure https
        # Ensure www for UI main domain, but be careful with subdomains
        parsed_url = urlparse(url)
        if parsed_url.netloc == 'ui.ac.id':
             url = url.replace('://ui.ac.id', '://www.ui.ac.id', 1)
        return url
    
    @staticmethod
    def log_bfs_discovery(url: str, stage: str, priority: int, link_text: str, depth: int) -> str:
        """Generate log message for BFS discovery (can be used with a logger)."""
        return f"🔍 BFS [{stage.upper()}] D{depth}: {link_text[:30]}... -> {url} (P:{priority})"