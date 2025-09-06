import json
import logging
import requests
import time
from pathlib import Path
from typing import Dict, List, Optional
from urllib.parse import unquote

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger('entities-scraper')

class EntitiesScraper:
    def __init__(self):
        self.api_base_url = None
        self.election_years = None
        self.entities = {}

    def scrape_entities(self, api_base_url: str, election_years: List[str]) -> Dict:
        """
        Main entry point for scraping entities from the election API.
        Returns complete entities dictionary for all election years.
        Preserves existing data and only adds new data.
        """
        self.api_base_url = api_base_url.rstrip('/')
        self.election_years = election_years
        
        try:
            for year in self.election_years:
                logger.info(f"Scraping entities for year {year}")
                # Initialize year data if not exists
                if year not in self.entities:
                    self.entities[year] = {
                        'fylke': [],
                        'kommune': [],
                        'krets': []
                    }
                
                # Create sets of existing IDs for efficient lookup
                existing_fylke = set(self.entities[year]['fylke'])
                existing_kommune = set(self.entities[year]['kommune'])
                existing_krets = set(self.entities[year]['krets'])
                
                # Start with national level to get fylke list
                national_url = f"{self.api_base_url}/{year}/st"
                national_data = self._fetch_data(national_url)
                if not national_data:
                    continue

                # Process fylke level
                for fylke in national_data.get('_links', {}).get('related', []):
                    fylke_id = self._create_fylke_id(fylke)
                    if fylke_id and fylke_id not in existing_fylke:
                        self.entities[year]['fylke'].append(fylke_id)
                        existing_fylke.add(fylke_id)
                        
                        # Process kommune level
                        kommune_url = f"{self.api_base_url}{fylke['href']}"
                        kommune_data = self._fetch_data(kommune_url)
                        if not kommune_data:
                            continue
                            
                        for kommune in kommune_data.get('_links', {}).get('related', []):
                            kommune_id = self._create_kommune_id(fylke, kommune)
                            if kommune_id and kommune_id not in existing_kommune:
                                self.entities[year]['kommune'].append(kommune_id)
                                existing_kommune.add(kommune_id)
                                
                                # Process krets level if available
                                if kommune.get('harUnderordnet', False):
                                    krets_url = f"{self.api_base_url}{kommune['href']}"
                                    krets_data = self._fetch_data(krets_url)
                                    if not krets_data:
                                        continue
                                        
                                    for krets in krets_data.get('_links', {}).get('related', []):
                                        krets_id = self._create_krets_id(fylke, kommune, krets)
                                        if krets_id and krets_id not in existing_krets:
                                            self.entities[year]['krets'].append(krets_id)
                                            existing_krets.add(krets_id)

            return self.entities

        except Exception as e:
            logger.error(f"Error scraping entities: {str(e)}")
            return {}

    def _fetch_data(self, url: str) -> Optional[Dict]:
        """Fetch data from API with error handling and retries"""
        max_retries = 5
        retry_delay = 1  # Initial delay in seconds
        
        for attempt in range(max_retries):
            try:
                #logger.info(f"------ Fetching data from {url}")
                response = requests.get(url, timeout=30)
                response.raise_for_status()
                return response.json()
            except requests.RequestException as e:
                if attempt == max_retries - 1:  # Last attempt
                    logger.error(f"Failed to fetch URL {url} after {max_retries} attempts: {str(e)}")
                    return None
                else:
                    wait_time = retry_delay * (2 ** attempt)  # Exponential backoff
                    logger.warning(f"URL {url}: Attempt {attempt + 1} failed, retrying in {wait_time} seconds: {str(e)}")
                    time.sleep(wait_time)

    def _normalize_name(self, name: str) -> str:
        """Convert Norwegian names to URL-safe identifiers"""
        # Remove special characters and convert to lowercase
        name = name.lower()
        
        # Handle Norwegian characters
        replacements = {
            'æ': 'ae',
            'ø': 'o',
            'å': 'a',
            ' ': '-',
            '.': '',
            ',': '',
            '+': '-og-'  # Common in Norwegian place names
        }
        
        for old, new in replacements.items():
            name = name.replace(old, new)
        
        # Remove any remaining non-alphanumeric characters except hyphens
        name = ''.join(c for c in name if c.isalnum() or c == '-')
        
        # Remove multiple consecutive hyphens
        while '--' in name:
            name = name.replace('--', '-')
        
        # Remove leading/trailing hyphens
        return name.strip('-')

    def _create_fylke_id(self, fylke: Dict) -> Optional[str]:
        """Create a fylke ID in the format 'fylke-{nr}-{name}'"""
        try:
            nr = fylke['nr']
            name = unquote(fylke['hrefNavn'].split('/')[-1])
            normalized_name = self._normalize_name(name)
            return f"fylke-{nr}-{normalized_name}"
        except (KeyError, IndexError) as e:
            logger.error(f"Error creating fylke ID: {str(e)}")
            return None

    def _create_kommune_id(self, fylke: Dict, kommune: Dict) -> Optional[str]:
        """Create a kommune ID in the format 'kommune-{fylke_nr}-{kommune_nr}-{name}'"""
        try:
            fylke_nr = fylke['nr']
            kommune_nr = kommune['nr']
            name = unquote(kommune['hrefNavn'].split('/')[-1])
            normalized_name = self._normalize_name(name)
            return f"kommune-{fylke_nr}-{kommune_nr}-{normalized_name}"
        except (KeyError, IndexError) as e:
            logger.error(f"Error creating kommune ID: {str(e)}")
            return None

    def _create_krets_id(self, fylke: Dict, kommune: Dict, krets: Dict) -> Optional[str]:
        """Create a krets ID in the format 'krets-{fylke_nr}-{kommune_nr}-{krets_nr}-{name}'"""
        try:
            fylke_nr = fylke['nr']
            kommune_nr = kommune['nr']
            krets_nr = krets['nr']
            name = unquote(krets['hrefNavn'].split('/')[-1])
            normalized_name = self._normalize_name(name)
            return f"krets-{fylke_nr}-{kommune_nr}-{krets_nr}-{normalized_name}"
        except (KeyError, IndexError) as e:
            logger.error(f"Error creating krets ID: {str(e)}")
            return None
