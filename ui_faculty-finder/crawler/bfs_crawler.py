# bfs_crawler.py
import requests
from bs4 import BeautifulSoup
from collections import deque
import time
import json
import re
from urllib.parse import urljoin, urlparse
import logging
import os

class NaturalUIFacultyCrawler:
    def __init__(self, base_url="https://www.ui.ac.id/", delay=1):
        self.base_url = base_url
        self.delay = delay
        self.visited = set()
        self.faculty_data = []
        self.navigation_path = []  # Track navigation path
        self.queue_history = []  # Track BFS queue for demonstration
        
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        })
        
        self.expected_faculties = {
            'Fakultas Farmasi', 'Fakultas Hukum', 'Fakultas Ilmu Administrasi',
            'Fakultas Ilmu Pengetahuan Budaya', 'Fakultas Ekonomi dan Bisnis',
            'Fakultas Ilmu Keperawatan', 'Fakultas Ilmu Komputer',
            'Fakultas Ilmu Sosial dan Ilmu Politik', 'Fakultas Kedokteran',
            'Fakultas Kedokteran Gigi', 'Fakultas Kesehatan Masyarakat',
            'Fakultas Matematika dan Ilmu Pengetahuan Alam', 'Fakultas Psikologi',
            'Fakultas Teknik', 'Program Pendidikan Vokasi',
            'Sekolah Ilmu Lingkungan', 'Sekolah Kajian Stratejik dan Global'
        }

        self.known_faculty_subdomains = [
            'https://fk.ui.ac.id/',      # Fakultas Kedokteran
            'https://eng.ui.ac.id/',    # Fakultas Teknik
            'https://law.ui.ac.id/',    # Fakultas Hukum
            'https://feb.ui.ac.id/',    # Fakultas Ekonomi dan Bisnis
            'https://psy.ui.ac.id/',    # Fakultas Psikologi
            'https://sci.ui.ac.id/',    # Fakultas MIPA
            'https://dent.ui.ac.id/',   # Fakultas Kedokteran Gigi
            'https://fisip.ui.ac.id/',  # Fakultas Ilmu Sosial dan Ilmu Politik
            'https://fib.ui.ac.id/',    # Fakultas Ilmu Pengetahuan Budaya
            'https://nursing.ui.ac.id/', # Fakultas Ilmu Keperawatan
            'https://cs.ui.ac.id/',     # Fakultas Ilmu Komputer
            'https://pharmacy.ui.ac.id/', # Fakultas Farmasi
            'https://pubhealth.ui.ac.id/', # Fakultas Kesehatan Masyarakat
            'https://adm.ui.ac.id/',    # Fakultas Ilmu Administrasi
            'https://vokasi.ui.ac.id/', # Program Pendidikan Vokasi
            'https://sil.ui.ac.id/',    # Sekolah Ilmu Lingkungan
            'https://sksg.ui.ac.id/',   # Sekolah Kajian Stratejik dan Global
        ]
        self.known_faculty_netlocs = {urlparse(fsd).netloc for fsd in self.known_faculty_subdomains if urlparse(fsd).netloc}

        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(levelname)s - %(message)s'
        )
        self.logger = logging.getLogger(__name__)
    
    def is_valid_url(self, url):
        """Check if URL is valid and belongs to UI domain"""
        try:
            parsed = urlparse(url)
            valid_domains = [
                'www.ui.ac.id', 'ui.ac.id',
                'fk.ui.ac.id', 'eng.ui.ac.id', 'law.ui.ac.id', 'feb.ui.ac.id',
                'psy.ui.ac.id', 'sci.ui.ac.id', 'dent.ui.ac.id', 'fisip.ui.ac.id',
                'fib.ui.ac.id', 'nursing.ui.ac.id', 'cs.ui.ac.id', 'pharmacy.ui.ac.id',
                'pubhealth.ui.ac.id', 'adm.ui.ac.id', 'vokasi.ui.ac.id',
                'sil.ui.ac.id', 'sksg.ui.ac.id',
                'ft.ui.ac.id', 'fvok.ui.ac.id'
            ]
            
            return (
                parsed.netloc in valid_domains and 
                parsed.scheme in ['http', 'https'] and
                not any(ext in url.lower() for ext in ['.pdf', '.doc', '.jpg', '.png', '.gif', '.zip', '.mp4', '.mp3'])
            )
        except:
            return False
    
    def get_page_content(self, url):
        """Fetch page content with improved error handling"""
        try:
            self.logger.info(f"🌐 Fetching: {url}")
            response = self.session.get(url, timeout=15)
            response.raise_for_status()
            return response.text
        except requests.exceptions.ConnectionError as e:
            if "Name or service not known" in str(e) or "getaddrinfo failed" in str(e):
                self.logger.error(f"❌ Domain tidak ditemukan: {url}")
            else:
                self.logger.error(f"❌ Koneksi error untuk {url}: {e}")
            return None
        except requests.RequestException as e:
            self.logger.error(f"❌ Request error untuk {url}: {e}")
            return None
    
    
    def get_navigation_priority_links(self, soup, current_url):
        """Get navigation links with smart priority for natural crawling"""
        links = []
        current_url_lower = current_url.lower()
        
        for link in soup.find_all('a', href=True):
            href = link['href']
            full_url = urljoin(current_url, href)
            
            if not self.is_valid_url(full_url) or full_url in self.visited:
                continue
            
            link_text = link.get_text().strip().lower()
            link_url_lower = full_url.lower()
            
            priority = 0
            navigation_stage = self.detect_navigation_stage(current_url)
            
            # Stage 1: From homepage, prioritize "Akademik" links
            if navigation_stage == 'homepage':
                if any(keyword in link_text for keyword in ['akademik', 'academic']):
                    priority += 50
                elif any(keyword in link_url_lower for keyword in ['akademik', 'academic']):
                    priority += 45
            
            # Stage 2: From akademik page, prioritize "Fakultas" links  
            elif navigation_stage == 'akademik':
                if any(keyword in link_text for keyword in ['fakultas', 'faculty']):
                    priority += 50
                elif any(keyword in link_url_lower for keyword in ['fakultas', 'faculty']):
                    priority += 45
            
            # Stage 3: From fakultas listing, prioritize individual faculty links
            elif navigation_stage == 'fakultas_list':
                faculty_keywords = [
                    'kedokteran', 'teknik', 'hukum', 'ekonomi', 'psikologi', 'matematika',
                    'farmasi', 'administrasi', 'budaya', 'keperawatan', 'komputer',
                    'kesehatan', 'vokasi', 'lingkungan', 'kajian', 'stratejik',
                    'ilmu komputer', 'ilmu keperawatan', 'ilmu administrasi', 'ilmu budaya',
                    'kedokteran gigi', 'kesehatan masyarakat', 'sosial dan politik',
                    'ekonomi dan bisnis', 'matematika dan ilmu pengetahuan alam',
                    'pendidikan vokasi', 'ilmu lingkungan', 'kajian stratejik dan global',
                    'gigi', 'sosial', 'politik', 'mipa', 'ipa', 'alam', 'pengetahuan',
                    'sekolah', 'program', 'global', 'vokasi', 'diploma', 'vocational',
                    'environmental', 'strategic', 'studies',
                    'fk', 'ft', 'fh', 'feb', 'fpsi', 'fmipa', 'fkg', 'fisip',
                    'fib', 'fik', 'fasilkom', 'fkm', 'fia', 'sil', 'sksg',
                    'vokui', 'pv', 'ui-voc', 'fvok',
                    'engineering', 'medicine', 'law', 'economics', 'psychology',
                    'pharmacy', 'administration', 'nursing', 'computer', 'health',
                    'mathematics', 'science', 'social', 'political', 'cultural',
                    'environment', 'strategic', 'vocational education'
                ]
                
                text_match = any(keyword in link_text for keyword in faculty_keywords)
                url_match = any(keyword in link_url_lower for keyword in faculty_keywords)
                
                missing_faculty_patterns = [
                    'teknik', 'engineering', 'ft.ui', 'fakultas teknik',
                    'vokasi', 'vocational', 'diploma', 'pendidikan vokasi', 'program pendidikan vokasi',
                    'lingkungan', 'environment', 'sil.ui', 'sekolah ilmu lingkungan',
                    'kajian', 'stratejik', 'global', 'strategic', 'sksg.ui', 'sekolah kajian'
                ]
                
                missing_faculty_boost = any(pattern in link_text or pattern in link_url_lower 
                                        for pattern in missing_faculty_patterns)
                
                if missing_faculty_boost:
                    priority += 60  # Extra boost for missing faculties
                elif text_match:
                    priority += 50
                elif url_match:
                    priority += 45
                elif 'fakultas' in link_url_lower or 'faculty' in link_url_lower:
                    priority += 40
            
            # General priority boosts
            if any(keyword in link_text for keyword in ['fakultas', 'faculty', 'sekolah', 'program']):
                priority += 20
            
            if any(keyword in link_url_lower for keyword in ['akademik', 'fakultas', 'faculty', 'sekolah']):
                priority += 15

            parsed_link_url = urlparse(full_url)
            if parsed_link_url.netloc in self.known_faculty_netlocs:
                priority += 35  # Significant boost
            
            link_parent = link.find_parent(['nav', 'ul', 'li'])
            if link_parent and any(class_name in str(link_parent.get('class', [])).lower() 
                                for class_name in ['menu', 'nav', 'navigation']):
                priority += 10
            
            low_priority_keywords = [
                'berita', 'news', 'pengumuman', 'agenda', 'gallery', 
                'download', 'kontak', 'contact', 'login', 'alumni'
            ]
            if any(keyword in link_text for keyword in low_priority_keywords):
                priority -= 5
            
            if priority > 0:
                links.append((full_url, priority, link_text, navigation_stage))
        
        links.sort(key=lambda x: x[1], reverse=True)
        return links
    
    def detect_navigation_stage(self, url):
        """Detect what stage of navigation we're in"""
        url_lower = url.lower()
        
        faculty_subdomains = [
            'fk.ui.ac.id', 'eng.ui.ac.id', 'law.ui.ac.id', 'feb.ui.ac.id',
            'psy.ui.ac.id', 'sci.ui.ac.id', 'dent.ui.ac.id', 'fisip.ui.ac.id',
            'fib.ui.ac.id', 'nursing.ui.ac.id', 'cs.ui.ac.id', 'pharmacy.ui.ac.id',
            'pubhealth.ui.ac.id', 'adm.ui.ac.id', 'vokasi.ui.ac.id',
            'sil.ui.ac.id', 'sksg.ui.ac.id', 'ft.ui.ac.id', 'fvok.ui.ac.id'
        ]
        
        if any(domain in url_lower for domain in faculty_subdomains):
            return 'specific_faculty'
        
        if url_lower == 'https://www.ui.ac.id/' or url_lower == 'https://ui.ac.id/':
            return 'homepage'
        elif 'akademik' in url_lower and 'fakultas' not in url_lower:
            return 'akademik'
        elif 'akademik/fakultas' in url_lower and not self._has_specific_faculty_in_url(url_lower):
            return 'fakultas_list'
        elif self._has_specific_faculty_in_url(url_lower) or any(indicator in url_lower for indicator in ['fakultas', 'faculty']):
            return 'specific_faculty'
        else:
            return 'other'
    
    def _has_specific_faculty_in_url(self, url_lower):
        """Check if URL contains specific faculty indicators"""
        specific_faculty_indicators = [
            # Existing patterns
            'kedokteran', 'teknik', 'hukum', 'ekonomi', 'psikologi', 'matematika', 
            'sekolah', 'program', 'pengetahuan', 'kesehatan', 'ilmu', 'administrasi', 
            'keperawatan', 'komputer', 'sosial', 'gigi', 'vokasi', 'lingkungan', 
            'kajian', 'budaya', 'farmasi', 'mipa', 'alam', 'bisnis',
            # Subdomain patterns
            'fk.ui', 'ft.ui', 'fh.ui', 'feb.ui', 'fpsi.ui', 'fmipa.ui', 
            'fkg.ui', 'fisip.ui', 'fib.ui', 'fik.ui', 'fasilkom.ui', 'fkm.ui', 'fvok.ui',
            'sil.ui', 'sksg.ui',
            # SPECIFIC patterns for missing faculties  
            'engineering', 'vocational', 'environment', 'strategic', 'global',
            'diploma', 'environmental', 'stratejik',
            # Path patterns for missing faculties
            '/teknik/', '/vokasi/', '/lingkungan/', '/kajian/', '/stratejik/',
            '/engineering/', '/vocational/', '/environment/', '/strategic/'
        ]
        return any(indicator in url_lower for indicator in specific_faculty_indicators)
    
    def extract_faculty_info(self, url, soup):
        """Extract faculty information from page"""
        faculty_info = {
            'url': url,
            'name': '',
            'description': '',
            'programs': [],
            'contact': {},
            'navigation_path': self.get_current_navigation_path(url),
            'departments': [],
            'faculty_type': self.detect_faculty_type(url, soup),
            'discovery_stage': self.detect_navigation_stage(url)
        }
        
        faculty_name = self.extract_faculty_name(url, soup)
        if faculty_name:
            faculty_info['name'] = faculty_name
        else:
            self.logger.warning(f"⚠️  Could not extract faculty name from {url}")
            return None
        
        faculty_info['description'] = self.extract_description(soup)
        faculty_info['programs'] = self.extract_programs(soup)
        faculty_info['departments'] = self.extract_departments(soup)
        faculty_info['contact'] = self.extract_contact_info(soup)
        
        return faculty_info
    
    def get_current_navigation_path(self, faculty_url):
        """Generate actual navigation path based on current URL"""
        stage = self.detect_navigation_stage(faculty_url)
        
        if stage == 'specific_faculty':
            return [
                {'name': 'Beranda UI', 'url': 'https://www.ui.ac.id/', 'stage': 'homepage'},
                {'name': 'Akademik', 'url': 'https://www.ui.ac.id/akademik/', 'stage': 'akademik'},
                {'name': 'Fakultas', 'url': 'https://www.ui.ac.id/akademik/fakultas/', 'stage': 'fakultas_list'},
                {'name': 'Detail Fakultas', 'url': faculty_url, 'stage': 'specific_faculty'}
            ]
        else:
            return [{'name': 'Current Page', 'url': faculty_url, 'stage': stage}]
    
    def _is_generic_faculty_term(self, text):
        """Check if text is a generic faculty term that shouldn't be treated as a faculty name"""
        if not text:
            return True
        
        text_lower = text.lower().strip()
        
        generic_terms = [
            'detail fakultas', 'fakultas', 'faculty', 'daftar fakultas', 'list of faculties',
            'fakultas - universitas indonesia', 'fakultas ui', 'akademik', 'academic',
            'universitas indonesia', 'ui', 'beranda', 'home', 'homepage', 'main page', 'halaman utama'
        ]
        
        for generic in generic_terms:
            if text_lower == generic or text_lower.startswith(generic + ' -') or text_lower.endswith('- ' + generic):
                return True
        
        if len(text_lower) < 3 or len(text_lower) > 200: # Very short or very long names
            return True
        
        return False

    def extract_faculty_name(self, url, soup):
        """Extract faculty name with ENHANCED subdomain mapping"""
        name = None
        
        # PRIORITY: Check subdomain mapping first for accurate names
        subdomain_mapping = {
            'fk.ui.ac.id': 'Fakultas Kedokteran',
            'eng.ui.ac.id': 'Fakultas Teknik',
            'ft.ui.ac.id': 'Fakultas Teknik',
            'law.ui.ac.id': 'Fakultas Hukum',
            'feb.ui.ac.id': 'Fakultas Ekonomi dan Bisnis',
            'psy.ui.ac.id': 'Fakultas Psikologi',
            'sci.ui.ac.id': 'Fakultas Matematika dan Ilmu Pengetahuan Alam',
            'dent.ui.ac.id': 'Fakultas Kedokteran Gigi',
            'fisip.ui.ac.id': 'Fakultas Ilmu Sosial dan Ilmu Politik',
            'fib.ui.ac.id': 'Fakultas Ilmu Pengetahuan Budaya',
            'nursing.ui.ac.id': 'Fakultas Ilmu Keperawatan',
            'cs.ui.ac.id': 'Fakultas Ilmu Komputer',
            'pharmacy.ui.ac.id': 'Fakultas Farmasi',
            'pubhealth.ui.ac.id': 'Fakultas Kesehatan Masyarakat',
            'adm.ui.ac.id': 'Fakultas Ilmu Administrasi',
            'vokasi.ui.ac.id': 'Program Pendidikan Vokasi',
            'fvok.ui.ac.id': 'Program Pendidikan Vokasi',
            'sil.ui.ac.id': 'Sekolah Ilmu Lingkungan',
            'sksg.ui.ac.id': 'Sekolah Kajian Stratejik dan Global'
        }
        
        parsed_url = urlparse(url)
        if parsed_url.netloc in subdomain_mapping:
            name = subdomain_mapping[parsed_url.netloc]
            self.logger.info(f"✅ Subdomain mapping: {parsed_url.netloc} -> {name}")
            return name
        
        # Strategy 1: Page title
        title = soup.find('title')
        if title:
            title_text = title.get_text().strip()
            patterns = [
                r'fakultas\s+([^-|]+)',
                r'([^-|]*fakultas[^-|]*)',
                r'(fk|ft|fh|feb|fpsi|fmipa|fkg|fisip|fib|fik|fasilkom|fkm|fvok)\s*[-:]?\s*([^-|]+)',
            ]
            for pattern in patterns:
                match = re.search(pattern, title_text, re.I)
                if match:
                    if len(match.groups()) == 1:
                        candidate_name = match.group(1).strip()
                    else:
                        candidate_name = f"{match.group(1)} {match.group(2)}".strip()
                    if not self._is_generic_faculty_term(candidate_name):
                        name = candidate_name
                        break
        
        # Strategy 2: H1, H2 tags
        if not name:
            h1_tags = soup.find_all(['h1', 'h2'])
            for h in h1_tags:
                h_text = h.get_text().strip()
                if (('fakultas' in h_text.lower() or 'faculty' in h_text.lower()) 
                    and len(h_text) < 150 and len(h_text) > 5
                    and not self._is_generic_faculty_term(h_text)):
                    name = h_text
                    break
        
        # Strategy 3: Meta tags
        if not name:
            meta_tags = soup.find_all('meta')
            for meta in meta_tags:
                content = meta.get('content', '').strip()
                if (content and 'fakultas' in content.lower() and len(content) < 100
                    and not self._is_generic_faculty_term(content)):
                    name = content
                    break
        
        # Strategy 4: URL-based extraction as fallback
        if not name:
            name = self.extract_name_from_url(url)
        
        if name:
            name = self.clean_faculty_name(name)
            if self._is_generic_faculty_term(name): # Final check
                return None
        
        return name
    
    def extract_name_from_url(self, url):
        """Extract faculty name from URL patterns"""
        url_lower = url.lower()
        
        url_patterns = {
            # Existing mappings
            'kedokteran': 'Fakultas Kedokteran', 'teknik': 'Fakultas Teknik', 'hukum': 'Fakultas Hukum',
            'ekonomi': 'Fakultas Ekonomi dan Bisnis', 'psikologi': 'Fakultas Psikologi',
            'matematika': 'Fakultas Matematika dan Ilmu Pengetahuan Alam', 'mipa': 'Fakultas Matematika dan Ilmu Pengetahuan Alam',
            'gigi': 'Fakultas Kedokteran Gigi', 'sosial': 'Fakultas Ilmu Sosial dan Ilmu Politik',
            'politik': 'Fakultas Ilmu Sosial dan Ilmu Politik', 'fisip': 'Fakultas Ilmu Sosial dan Ilmu Politik',
            'budaya': 'Fakultas Ilmu Pengetahuan Budaya', 'fib': 'Fakultas Ilmu Pengetahuan Budaya',
            'keperawatan': 'Fakultas Ilmu Keperawatan', 'fik': 'Fakultas Ilmu Keperawatan',
            'kesehatan': 'Fakultas Kesehatan Masyarakat', 'fkm': 'Fakultas Kesehatan Masyarakat',
            'komputer': 'Fakultas Ilmu Komputer', 'fasilkom': 'Fakultas Ilmu Komputer',
            'farmasi': 'Fakultas Farmasi', 'administrasi': 'Fakultas Ilmu Administrasi',
            # Enhanced patterns for missing faculties
            'vokasi': 'Program Pendidikan Vokasi', 'vocational': 'Program Pendidikan Vokasi',
            'diploma': 'Program Pendidikan Vokasi', 'pendidikan vokasi': 'Program Pendidikan Vokasi',
            'program pendidikan vokasi': 'Program Pendidikan Vokasi', 'vokui': 'Program Pendidikan Vokasi', 'fvok': 'Program Pendidikan Vokasi',
            'lingkungan': 'Sekolah Ilmu Lingkungan', 'environment': 'Sekolah Ilmu Lingkungan',
            'environmental': 'Sekolah Ilmu Lingkungan', 'ilmu lingkungan': 'Sekolah Ilmu Lingkungan',
            'sekolah ilmu lingkungan': 'Sekolah Ilmu Lingkungan', 'sil': 'Sekolah Ilmu Lingkungan', 'sil.ui': 'Sekolah Ilmu Lingkungan',
            'kajian': 'Sekolah Kajian Stratejik dan Global', 'stratejik': 'Sekolah Kajian Stratejik dan Global',
            'strategic': 'Sekolah Kajian Stratejik dan Global', 'global': 'Sekolah Kajian Stratejik dan Global',
            'kajian stratejik': 'Sekolah Kajian Stratejik dan Global', 'sekolah kajian': 'Sekolah Kajian Stratejik dan Global',
            'sksg': 'Sekolah Kajian Stratejik dan Global', 'sksg.ui': 'Sekolah Kajian Stratejik dan Global',
            'engineering': 'Fakultas Teknik', 'ft.ui': 'Fakultas Teknik', 'fakultas teknik': 'Fakultas Teknik'
        }
        
        for pattern, faculty_name in url_patterns.items():
            if pattern in url_lower:
                return faculty_name
        return None
    
    def clean_faculty_name(self, name):
        """Clean faculty name"""
        if not name:
            return ""
        
        name = re.sub(r'^(fakultas|faculty|universitas indonesia|ui)\s*[-|:]?\s*', '', name, flags=re.I)
        name = re.sub(r'\s*[-|:]\s*(universitas indonesia|ui|fakultas|faculty).*$', '', name, flags=re.I)
        name = re.sub(r'\s*-\s*.*$', '', name)
        name = re.sub(r'^detail\s+', '', name, flags=re.I) # Remove "Detail" prefix
        name = re.sub(r'\s+', ' ', name).strip()
        
        if name and not self._is_generic_faculty_term(name):
            if not name.lower().startswith(('fakultas', 'sekolah', 'program')):
                name = f"Fakultas {name}"
        
        return name.strip()

    
    def extract_description(self, soup):
        """Extract description"""
        description = ""
        meta_desc = soup.find('meta', {'name': 'description'})
        if meta_desc:
            description = meta_desc.get('content', '').strip()
        
        if not description:
            paragraphs = soup.find_all('p')
            for p in paragraphs:
                p_text = p.get_text().strip()
                if len(p_text) > 50 and not p_text.startswith('Copyright'):
                    description = p_text
                    break
        
        if description and len(description) > 300:
            description = description[:300] + '...'
        return description
    
    def extract_programs(self, soup):
        """Extract study programs"""
        programs = set()
        program_keywords = ['program studi', 'prodi', 'jurusan', 'sarjana', 'magister', 'doktor', 's1', 's2', 's3']
        
        for ul in soup.find_all(['ul', 'ol']):
            for li in ul.find_all('li'):
                li_text = li.get_text().strip()
                if (10 < len(li_text) < 150 and 
                    any(keyword in li_text.lower() for keyword in program_keywords)):
                    programs.add(li_text)
        
        page_text = soup.get_text()
        lines = page_text.split('\n')
        for line in lines:
            line = line.strip()
            if (any(keyword in line.lower() for keyword in program_keywords) and 
                10 < len(line) < 100):
                programs.add(line)
        
        return list(programs)[:15]
    
    def extract_departments(self, soup):
        """Extract departments"""
        departments = set()
        dept_keywords = ['departemen', 'department', 'bagian']
        
        page_text = soup.get_text()
        lines = page_text.split('\n')
        
        for line in lines:
            line = line.strip()
            if (any(keyword in line.lower() for keyword in dept_keywords) and 
                10 < len(line) < 80):
                departments.add(line)
        
        return list(departments)[:8]
    
    def extract_contact_info(self, soup):
        """Extract contact information"""
        contact = {}
        page_text = soup.get_text()
        
        email_pattern = r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}'
        emails = re.findall(email_pattern, page_text)
        if emails:
            valid_emails = [email for email in emails if not any(skip in email.lower() 
                          for skip in ['noreply', 'admin', 'webmaster'])]
            if valid_emails:
                contact['email'] = valid_emails[0]
        
        phone_pattern = r'(?:\+62|62|0)[0-9\-\s\(\)]{8,15}'
        phones = re.findall(phone_pattern, page_text)
        if phones:
            contact['phone'] = phones[0]
        
        return contact
    
    def detect_faculty_type(self, url, soup):
        """Detect faculty page type"""
        return self.detect_navigation_stage(url) # Simplified
    
    def is_faculty_page(self, url, soup):
        """Determine if current page is a faculty page"""
        url_lower = url.lower()
        page_text_lower = soup.get_text().lower() 
        title_tag = soup.find('title')
        title_text_lower = title_tag.get_text().strip().lower() if title_tag else ""

        # --- Exclusion Rules ---
        generic_faculty_listing_url_patterns = [r'/akademik/fakultas/?$', r'/fakultas/?$']
        if any(re.search(pattern, url_lower) for pattern in generic_faculty_listing_url_patterns):
            return False
        
        generic_titles = [
            r'^fakultas\s*-\s*universitas\s*indonesia\s*$', r'^fakultas\s*ui\s*$',
            r'^daftar\s*fakultas', r'^fakultas\s*$',
            r'^academic\s*-\s*universitas\s*indonesia\s*$', r'^academic\s*-\s*ui\s*$',
            r'^akademik\s*-\s*universitas\s*indonesia\s*$', r'^akademik\s*ui\s*$',
            r'^detail\s*fakultas\s*$' 
        ]
        if any(re.search(pattern, title_text_lower) for pattern in generic_titles):
            return False

        parsed_page_url_for_exclusion_check = urlparse(url)
        page_netloc_for_exclusion = parsed_page_url_for_exclusion_check.netloc
        is_root_of_known_subdomain_for_exclusion = (page_netloc_for_exclusion in self.known_faculty_netlocs and
                                                    parsed_page_url_for_exclusion_check.path.strip('/') == '')

        dean_leadership_url_patterns = [
            r'/(dekan|profil-dekan|sambutan-dekan)($|/|_)',
            r'/(pimpinan|struktur-pimpinan|profil-pimpinan|manajemen)($|/|_)',
            r'/staff($|/|[-_])(dosen|akademik|pengajar|list|direktori)?',
            r'/dosen($|/|[-_])(profil|list|daftar)?',
            r'/profil[-_](dosen|staf|pegawai)($|/)', r'/direktori[-_](dosen|staf|pegawai)($|/)',
            r'/guru-besar($|/)'
        ]
        if not is_root_of_known_subdomain_for_exclusion:
            if any(re.search(pattern, url_lower) for pattern in dean_leadership_url_patterns):
                return False

        main_heading_text_lower = ""
        h1 = soup.find('h1')
        if h1: main_heading_text_lower += h1.get_text().strip().lower() + " "
        h2 = soup.find('h2') 
        if h2: main_heading_text_lower += h2.get_text().strip().lower()

        dean_leadership_title_heading_keywords = [
            'dekan fakultas', 'profil dekan', 'sambutan dekan', 'kata dekan', 'wakil dekan',
            'pimpinan fakultas', 'struktur pimpinan', 'manajemen fakultas', 'profil pimpinan',
            'daftar dosen', 'staff direktori', 'direktori dosen', 'profil dosen', 'guru besar kami',
            'tenaga pengajar', 'staf pengajar', 'staf akademik', 'struktur organisasi universitas indonesia'
        ]
        if not is_root_of_known_subdomain_for_exclusion:
            page_title_or_heading_is_dean_focused = any(keyword in title_text_lower or keyword in main_heading_text_lower
                                                        for keyword in dean_leadership_title_heading_keywords)
            if page_title_or_heading_is_dean_focused:
                return False
        
        if 'detail fakultas' in title_text_lower or ('detail fakultas' in page_text_lower and len(page_text_lower) < 1000):
            specific_faculty_name_keywords_in_detail = [
                'kedokteran', 'teknik', 'hukum', 'ekonomi', 'psikologi', 'matematika', 'mipa', 'farmasi', 
                'administrasi', 'budaya', 'fib', 'keperawatan', 'fik', 'komputer', 'fasilkom', 'kesehatan', 'fkm',
                'sosial', 'politik', 'fisip', 'gigi', 'fkg', 'vokasi', 'lingkungan', 'sil', 'kajian', 'stratejik', 'global', 'sksg'
            ]
            if not any(specific_keyword in page_text_lower for specific_keyword in specific_faculty_name_keywords_in_detail) and \
               not any(specific_keyword in title_text_lower for specific_keyword in specific_faculty_name_keywords_in_detail):
                return False
        
        # --- Positive Identification Scoring System ---
        faculty_score = 0
        parsed_page_url = urlparse(url)
        page_netloc = parsed_page_url.netloc
        is_on_known_faculty_subdomain = page_netloc in self.known_faculty_netlocs
        is_root_of_known_subdomain = is_on_known_faculty_subdomain and (parsed_page_url.path.strip('/') == '')

        if is_on_known_faculty_subdomain: faculty_score += 50 
        if is_root_of_known_subdomain: faculty_score += 10

        specific_faculty_url_patterns = [
            'fk.ui.ac.id', 'ft.ui.ac.id', 'eng.ui.ac.id', 'fh.ui.ac.id', 'feb.ui.ac.id', 'psy.ui.ac.id',
            'sci.ui.ac.id', 'fmipa.ui.ac.id', 'dent.ui.ac.id', 'fkg.ui.ac.id', 'fisip.ui.ac.id', 'fib.ui.ac.id',
            'nursing.ui.ac.id', 'fik.ui.ac.id', 'cs.ui.ac.id', 'fasilkom.ui.ac.id', 'pubhealth.ui.ac.id', 'fkm.ui.ac.id',
            'adm.ui.ac.id', 'fia.ui.ac.id', 'pharmacy.ui.ac.id', 'sil.ui.ac.id', 'sksg.ui.ac.id', 'vokasi.ui.ac.id', 'fvok.ui.ac.id',
            r'/fakultas[/-](kedokteran|teknik|hukum|ekonomi|psikologi|matematika|farmasi|administrasi|budaya|keperawatan|komputer|kesehatan|sosial|gigi)',
            r'/(fk|kedokteran)/', r'/(ft|teknik|engineering)/', r'/(fh|hukum|law)/', r'/(feb|ekonomi)/', 
            r'/(fpsi|psikologi)/', r'/(fmipa|sci|matematika)/', r'/(ff|farmasi|pharmacy)/', r'/(fia|adm|administrasi)/',
            r'/(fib|budaya)/', r'/(fik|nursing|keperawatan)/', r'/(fasilkom|cs|komputer)/', r'/(fkm|pubhealth|kesehatan)/', 
            r'/(fisip|sosial|politik)/', r'/(fkg|dent|gigi)/', r'/(vokasi|fvok|vocational|diploma)/',
            r'/(sil|lingkungan|environment)/', r'/(sksg|kajian|stratejik|strategic|global)/',
            r'/program.*vokasi', r'/pendidikan.*vokasi', r'/sekolah.*lingkungan',
            r'/sekolah.*kajian', r'/kajian.*stratejik', r'/stratejik.*global'
        ]
        if any(re.search(pattern, url_lower) for pattern in specific_faculty_url_patterns): faculty_score += 30
        
        og_site_name_tag = soup.find('meta', property='og:site_name')
        if og_site_name_tag and og_site_name_tag.get('content'):
            og_site_name_content = og_site_name_tag.get('content').lower()
            if any(keyword in og_site_name_content for keyword in ['fakultas', 'sekolah', 'program', 'faculty', 'school', 'vocational', 'vokasi', 'pharmacy', 'teknik', 'lingkungan']):
                faculty_score += 15

        og_type_tag = soup.find('meta', property='og:type')
        if og_type_tag and og_type_tag.get('content', '').lower() == 'school': faculty_score += 10

        specific_faculty_content_indicators = [
            'dekan', 'dean', 'wakil dekan', 'vice dean', 'pimpinan fakultas', 'struktur organisasi fakultas',
            'organisasi fakultas', 'senat akademik fakultas', 'sejarah fakultas', 'visi misi fakultas', 'profil fakultas',
            'tentang fakultas', 'sejarah sekolah', 'visi misi sekolah', 'profil sekolah', 'tentang sekolah',
            'sejarah program', 'visi misi program', 'profil program', 'tentang program', 'program studi', 'prodi',
            'departemen', 'department', 'jurusan', 'guru besar', 'dosen tetap fakultas', 'direktur program',
            'ketua program studi', 'kepala sekolah', 'direktur sekolah', 'program vokasi', 'pendidikan vokasi',
            'program diploma', 'ilmu lingkungan', 'kajian stratejik', 'kajian global', 'fakultas farmasi ui', 'sekolah ilmu lingkungan ui'
        ]
        content_specific_matches = sum(1 for indicator in specific_faculty_content_indicators if indicator in page_text_lower)
        if content_specific_matches >= 3: faculty_score += 25
        elif content_specific_matches >= 1: faculty_score += 15
        
        if any(expected_name.lower() in page_text_lower for expected_name in self.expected_faculties): faculty_score += 20
        
        hierarchy_indicators = ['kaprodi', 'ketua departemen', 'sekretaris fakultas']
        if sum(1 for indicator in hierarchy_indicators if indicator in page_text_lower) >= 1: faculty_score += 10

        faculty_sections_found = False
        for section_tag in soup.find_all(['div', 'section'], class_=re.compile(r'(faculty|fakultas|academic|dean|sekolah|program|departemen|department)', re.I), limit=5):
            if len(section_tag.get_text(strip=True)) > 100: faculty_sections_found = True; break
        if faculty_sections_found: faculty_score += 10
        
        program_list_found = False
        for ul_ol in soup.find_all(['ul', 'ol'], limit=10):
            ul_ol_text = ul_ol.get_text(" ", strip=True).lower()
            if any(prog_keyword in ul_ol_text for prog_keyword in ['program studi', 'sarjana', 'magister', 'doktor', 'diploma', 'spesialis', 'profesi']):
                if len(ul_ol.find_all('li')) > 1: program_list_found = True; break
        if program_list_found: faculty_score += 10

        program_level_keywords = ['sarjana (s1)', 's1-', 'magister (s2)', 's2-', 'doktor (s3)', 's3-', 'program profesi', 'program spesialis', 'program diploma']
        program_level_hits = sum(1 for keyword in program_level_keywords if keyword in page_text_lower)
        if program_level_hits >= 2: faculty_score += 15
        elif program_level_hits == 1: faculty_score += 5

        # --- Final Decision ---
        is_faculty = False
        faculty_page_threshold_on_subdomain_root = 60 
        faculty_page_threshold_on_subdomain_other = 55 
        faculty_page_threshold_general = 35     

        if is_root_of_known_subdomain:
            if faculty_score >= faculty_page_threshold_on_subdomain_root: is_faculty = True
        elif is_on_known_faculty_subdomain: 
            if faculty_score >= faculty_page_threshold_on_subdomain_other: is_faculty = True
        
        if not is_faculty and faculty_score >= faculty_page_threshold_general: is_faculty = True
        
        very_generic_titles_final_check = ['kontak', 'berita', 'artikel', 'pengumuman', 'agenda', 'login', 'pendaftaran']
        if is_faculty and any(vg_title in title_text_lower for vg_title in very_generic_titles_final_check) and faculty_score < 70:
            if len(soup.find_all('article')) > 3 and 'fakultas' not in title_text_lower and 'sekolah' not in title_text_lower:
                is_faculty = False
        
        return is_faculty
    
    def natural_crawl_bfs(self, max_depth=6, max_pages=100):
        """Natural BFS crawling following UI website navigation, stops when all faculties are found"""
        queue = deque([(self.base_url, 0, 'homepage')])
        pages_crawled = 0
        
        self.logger.info(f"🚀 Starting ENHANCED NATURAL BFS crawl from {self.base_url}")
        self.logger.info(f"📊 Following natural navigation: Homepage -> Akademik -> Fakultas -> Individual Faculty")
        self.logger.info(f"🎯 Parameters: max_depth={max_depth}, max_pages={max_pages}")
        self.logger.info(f"🔍 TARGET: Find all {len(self.expected_faculties)} faculties")
        
        while queue and pages_crawled < max_pages:
            current_url, depth, stage = queue.popleft()
            
            if current_url in self.visited or depth > max_depth:
                continue
            
            self.visited.add(current_url)
            self.logger.info(f"🔍 [{stage.upper()}] Depth {depth}: {current_url}")
            
            self.queue_history.append({
                'url': current_url, 'depth': depth, 'stage': stage,
                'queue_size': len(queue), 'visited_count': len(self.visited)
            })
            
            html_content = self.get_page_content(current_url)
            if not html_content:
                continue
            
            soup = BeautifulSoup(html_content, 'html.parser')
            pages_crawled += 1
            
            if self.is_faculty_page(current_url, soup):
                faculty_info = self.extract_faculty_info(current_url, soup)
                if faculty_info and faculty_info['name']:
                    if faculty_info['name'] not in [f['name'] for f in self.faculty_data]:
                        self.faculty_data.append(faculty_info)
                        self.logger.info(f"✅ FOUND FACULTY: {faculty_info['name']}")
                        self.logger.info(f"   📍 Discovery Path: {' -> '.join([step['name'] for step in faculty_info['navigation_path']])}")
                        self.logger.info(f"   📊 Programs: {len(faculty_info['programs'])}, Contact: {bool(faculty_info['contact'])}")
                        self.logger.info(f"   🎯 Progress: {len(self.faculty_data)}/{len(self.expected_faculties)} faculties found")

                        current_found_faculty_names = {f['name'] for f in self.faculty_data}
                        if self.expected_faculties.issubset(current_found_faculty_names):
                            self.logger.info(
                                f"🎉🎉🎉 All {len(self.expected_faculties)} expected faculties have been found! Halting crawl."
                            )
                            break 
                    else:
                        self.logger.info(f"⚠️ DUPLICATE FACULTY SKIPPED: {faculty_info['name']}")
            
            if depth < max_depth:
                priority_links = self.get_navigation_priority_links(soup, current_url)
                max_links_per_stage = {'homepage': 10, 'akademik': 15, 'fakultas_list': 30, 'specific_faculty': 10, 'other': 8}
                max_links = max_links_per_stage.get(stage, 8)
                
                added_count = 0
                for link_url, priority, link_text, _ in priority_links:
                    if link_url not in self.visited and added_count < max_links:
                        next_stage = self.detect_navigation_stage(link_url)
                        queue.append((link_url, depth + 1, next_stage))
                        added_count += 1
            
            time.sleep(self.delay)
        
        self.logger.info(f"🏁 Enhanced natural crawling completed!")
        self.logger.info(f"📈 Results: {len(self.faculty_data)} faculties discovered naturally")
        self.logger.info(f"📄 Pages crawled: {pages_crawled}")
        
        found_names = {f['name'] for f in self.faculty_data}
        missing_faculties = [expected for expected in self.expected_faculties if expected not in found_names and 
                             not any(expected.lower() in found.lower() or found.lower() in expected.lower() for found in found_names)]

        if missing_faculties:
            self.logger.warning(f"⚠️ Still missing {len(missing_faculties)} faculties: {missing_faculties}")
        elif len(self.faculty_data) >= len(self.expected_faculties):
            self.logger.info(f"🎉 SUCCESS! All {len(self.expected_faculties)} expected faculties were found!")
        else:
            self.logger.info(f"Crawl ended. Found {len(self.faculty_data)} out of {len(self.expected_faculties)}.")

        return self.faculty_data
    
    def save_results(self, filename='data/natural_faculty_data.json'):
        """Save crawling results"""
        os.makedirs(os.path.dirname(filename), exist_ok=True)
        
        save_data = {
            'crawl_info': {
                'timestamp': time.strftime('%Y-%m-%d %H:%M:%S'),
                'method': 'Natural BFS Navigation',
                'base_url': self.base_url,
                'total_faculties': len(self.faculty_data),
                'pages_crawled': len(self.visited),
                'navigation_stages': self.get_stage_summary()
            },
            'faculties': self.faculty_data,
            'crawl_path': self.queue_history[-20:]  # Last 20 crawl steps
        }
        
        with open(filename, 'w', encoding='utf-8') as f:
            json.dump(save_data, f, ensure_ascii=False, indent=2)
        
        self.logger.info(f"💾 Results saved to {filename}")
    
    def get_stage_summary(self):
        """Get summary of navigation stages visited"""
        stages = {}
        for item in self.queue_history:
            stage = item.get('stage', 'unknown')
            stages[stage] = stages.get(stage, 0) + 1
        return stages
    
    def get_crawl_summary(self):
        """Get detailed crawl summary"""
        summary = {
            'total_faculties': len(self.faculty_data),
            'pages_visited': len(self.visited),
            'navigation_stages': self.get_stage_summary(),
            'discovery_paths': [],
            'faculties': []
        }
        
        for faculty in self.faculty_data:
            faculty_summary = {
                'name': faculty['name'], 'url': faculty['url'],
                'discovery_stage': faculty.get('discovery_stage', 'unknown'),
                'navigation_path': [step['name'] for step in faculty.get('navigation_path', [])],
                'programs_count': len(faculty.get('programs', [])),
                'has_contact': bool(faculty.get('contact'))
            }
            summary['faculties'].append(faculty_summary)
            
            path_str = ' -> '.join(faculty_summary['navigation_path'])
            if path_str not in summary['discovery_paths']:
                summary['discovery_paths'].append(path_str)
        
        return summary