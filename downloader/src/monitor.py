import os
import json
import time
import logging
from datetime import datetime
from time import sleep
from pathlib import Path
from typing import Dict, Optional

import requests
from entities_scraper import EntitiesScraper

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger('election-monitor')

class ElectionMonitor:
    def __init__(self, api_base_url: str, data_path: str, election_years: list):
        self.api_base_url = api_base_url.rstrip('/')
        self.data_path = Path(data_path)
        self.election_years = election_years
        
        # Polling intervals in seconds
        self.schedules = {
            'nasjonalt': 300,  # 5 minutes
            'fylke': 600,      # 10 minutes
            'kommune': 900,    # 15 minutes
            'krets': 3600      # 1 hour
        }
        
        # API endpoint patterns
        self.endpoints = {
            'nasjonalt': "/{year}/st",
            'fylke': "/{year}/st/{fylke_nr}",
            'kommune': "/{year}/st/{fylke_nr}/{kommune_nr}",
            'krets': "/{year}/st/{fylke_nr}/{kommune_nr}/{krets_nr}"
        }
        
        # Load entity configuration
        self.entities = self._load_entities()
        
        # Ensure data directories exist
        self._init_directories()

    def _load_entities(self) -> dict:
        """Load and update entity configuration from JSON file"""
        config_path = self.data_path / 'config' / 'entities.json'
        config_dir = config_path.parent
        config_dir.mkdir(parents=True, exist_ok=True)

        # Try to load existing configuration
        existing_entities = {}
        if config_path.exists():
            try:
                with open(config_path, 'r', encoding='utf-8') as f:
                    existing_entities = json.load(f)
            except json.JSONDecodeError as e:
                logger.error(f"Invalid JSON in entity configuration: {str(e)}")

        # Scrape current entities
        logger.info("Scraping current entities from API...")
        scraper = EntitiesScraper()
        scraped_entities = scraper.scrape_entities(self.api_base_url, self.election_years)

        # If scraping succeeded, update the file
        if scraped_entities:
            logger.info("Updating entities.json with scraped data")
            with open(config_path, 'w', encoding='utf-8') as f:
                json.dump(scraped_entities, f, ensure_ascii=False, indent=2)
            return scraped_entities
        
        # If scraping failed, use existing configuration
        logger.warning("Using existing entities configuration")
        return existing_entities

    def _init_directories(self):
        """Create required directory structure"""
        for year in self.election_years:
            year_path = self.data_path / str(year)
            for entity_type in ['nasjonalt/norge', 'fylke', 'kommune', 'kommune/krets']:
                (year_path / entity_type).mkdir(parents=True, exist_ok=True)

    def _fetch_data(self, url: str) -> Optional[dict]:
        """Fetch data from API with error handling and retries"""
        max_retries = 5
        retry_delay = 1  # Initial delay in seconds
        
        for attempt in range(max_retries):
            try:
                response = requests.get(f"{self.api_base_url}{url}", timeout=30)
                response.raise_for_status()
                return response.json()
            except requests.RequestException as e:
                if attempt == max_retries - 1:  # Last attempt
                    logger.error(f"Failed to fetch URL {self.api_base_url}{url} after {max_retries} attempts: {str(e)}")
                    return None
                else:
                    wait_time = retry_delay * (2 ** attempt)  # Exponential backoff
                    logger.warning(f"URL {self.api_base_url}{url}: Attempt {attempt + 1} failed, retrying in {wait_time} seconds: {str(e)}")
                    sleep(wait_time)

    def _has_meaningful_changes(self, old_data: dict, new_data: dict) -> bool:
        """
        Compare data excluding metadata fields
        Returns True if meaningful changes detected
        """
        def clean_data(data: dict) -> dict:
            return data
            # Deep copy and remove metadata
            cleaned = json.loads(json.dumps(data))
            cleaned.pop('tidspunkt', None)
            if '_links' in cleaned:
                for link in cleaned['_links'].get('related', []):
                    link.pop('rapportGenerert', None)
            return cleaned

        old_clean = clean_data(old_data)
        new_clean = clean_data(new_data)
        
        return json.dumps(old_clean, sort_keys=True) != json.dumps(new_clean, sort_keys=True)

    def _save_snapshot(self, data: dict, entity_path: Path, timestamp: str):
        """Save data snapshot and update symlink"""
        # Create entity directory if it doesn't exist
        entity_path.mkdir(parents=True, exist_ok=True)
        
        # Save new snapshot
        snapshot_path = entity_path / f"{timestamp}.json"
        with open(snapshot_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        
        # Update symlink to latest
        symlink_path = entity_path.parent / f"{entity_path.name}.json"
        if symlink_path.exists():
            symlink_path.unlink()
        symlink_path.symlink_to(snapshot_path.relative_to(symlink_path.parent))
        
        logger.info(f"Saved new snapshot: {snapshot_path}")

    def process_entity(self, entity_type: str, entity_id: str, year: str):
        """Process a single entity, saving data if changed"""
        # Construct API URL and local path
        if entity_type == 'nasjonalt':
            url = self.endpoints[entity_type].format(year=year)
            entity_path = self.data_path / year / entity_type / 'norge'
        else:
            # Parse entity ID components (now includes descriptive name)
            base_id = '-'.join(entity_id.split('-')[:-1])  # Remove descriptive part
            components = base_id.split('-')
            
            if entity_type == 'fylke':
                url = self.endpoints[entity_type].format(year=year, fylke_nr=components[1])
            elif entity_type == 'kommune':
                url = self.endpoints[entity_type].format(
                    year=year, 
                    fylke_nr=components[1],
                    kommune_nr=components[2]
                )
            elif entity_type == 'krets':
                url = self.endpoints[entity_type].format(
                    year=year,
                    fylke_nr=components[1],
                    kommune_nr=components[2],
                    krets_nr=components[3]
                )
            entity_path = self.data_path / year / entity_type / entity_id

        # Fetch current data
        data = self._fetch_data(url)
        if not data:
            return
            
        timestamp = datetime.now().strftime("%Y-%m-%d__%H%M")
        
        # Check for existing data
        latest_link = entity_path.parent / f"{entity_path.name}.json"
        if latest_link.exists() and latest_link.is_symlink():
            with open(latest_link, 'r', encoding='utf-8') as f:
                previous_data = json.load(f)
                
            if self._has_meaningful_changes(previous_data, data):
                self._save_snapshot(data, entity_path, timestamp)
        else:
            # First time download
            self._save_snapshot(data, entity_path, timestamp)

    def run(self):
        """Main monitoring loop"""
        last_run: Dict[str, float] = {}
        
        while True:
            current_time = time.time()
            
            for year in self.election_years:
                year_config = self.entities.get(str(year), {})
                
                # Process national level
                if current_time - last_run.get('nasjonalt', 0) >= self.schedules['nasjonalt']:
                    self.process_entity('nasjonalt', 'norge', year)
                    last_run['nasjonalt'] = current_time
                
                # Process counties (fylke)
                if current_time - last_run.get('fylke', 0) >= self.schedules['fylke']:
                    for fylke_id in year_config.get('fylke', []):
                        self.process_entity('fylke', fylke_id, year)
                    last_run['fylke'] = current_time
                
                # Process municipalities
                if current_time - last_run.get('kommune', 0) >= self.schedules['kommune']:
                    for kommune_id in year_config.get('kommune', []):
                        self.process_entity('kommune', kommune_id, year)
                    last_run['kommune'] = current_time
                
                # Process voting districts
                if current_time - last_run.get('krets', 0) >= self.schedules['krets']:
                    for krets_id in year_config.get('krets', []):
                        self.process_entity('krets', krets_id, year)
                    last_run['krets'] = current_time
                
            # Sleep for a short interval before next check
            time.sleep(60)  # Check every minute

if __name__ == "__main__":
    # Load configuration from environment
    api_base_url = os.getenv('API_BASE_URL', 'https://valgresultat.no/api')
    data_path = os.getenv('DATA_PATH', './data')
    election_years = os.getenv('ELECTION_YEARS', '2021,2025,2029').split(',')
    
    logger.info(f"Starting ElectionMonitor")
    logger.info(f"Using data path: {data_path}")
    logger.info(f"Using API base URL: {api_base_url}")
    logger.info(f"Using election years: {election_years}")


    monitor = ElectionMonitor(api_base_url, data_path, election_years)
    monitor.run()
