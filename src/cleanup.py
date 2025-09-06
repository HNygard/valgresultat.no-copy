import os
import json
import logging
from datetime import datetime, timedelta
from pathlib import Path
from typing import List

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger('election-cleanup')

class DataRetentionManager:
    def __init__(self, data_path: str):
        self.data_path = Path(data_path)
        
        # Retention policies (in days)
        self.retention_periods = {
            'election_active': {  # During election period
                'nasjonalt': 365,  # Keep all national data for 1 year
                'fylke': 180,     # Keep county data for 6 months
                'kommune': 90,    # Keep municipality data for 3 months
                'krets': 30       # Keep district data for 1 month
            },
            'election_inactive': {  # Outside election period
                'nasjonalt': 'all',  # Keep all national data
                'fylke': 'latest',   # Keep only latest snapshot
                'kommune': 'latest',  # Keep only latest snapshot
                'krets': 'latest'    # Keep only latest snapshot
            }
        }

    def is_election_active(self, timestamp: datetime) -> bool:
        """
        Determine if a given timestamp is within an election period
        For now, consider September-October as election period
        """
        return timestamp.month in [9, 10]

    def get_snapshots(self, entity_path: Path) -> List[Path]:
        """Get all snapshot files for an entity, sorted by timestamp"""
        if not entity_path.exists():
            return []
            
        snapshots = [f for f in entity_path.glob('*.json') if f.name != f"{entity_path.name}.json"]
        return sorted(snapshots, key=lambda x: x.name)

    def should_retain_snapshot(self, snapshot: Path, entity_type: str, is_active: bool) -> bool:
        """Determine if a snapshot should be retained based on policy"""
        # Parse timestamp from filename (YYYY-MM-DD__HHMM)
        try:
            timestamp = datetime.strptime(snapshot.stem, "%Y-%m-%d__%H%M")
        except ValueError:
            logger.warning(f"Invalid timestamp format in filename: {snapshot}")
            return True  # Retain files with invalid timestamps for manual review
            
        # Get retention period based on election status
        policy = self.retention_periods['election_active' if is_active else 'election_inactive']
        retention = policy[entity_type]
        
        if retention == 'all':
            return True
        elif retention == 'latest':
            # This will be handled separately to keep the latest snapshot
            return True
        else:
            # Keep if within retention period
            cutoff = datetime.now() - timedelta(days=retention)
            return timestamp >= cutoff

    def cleanup_entity(self, entity_path: Path, entity_type: str):
        """Clean up old snapshots for a single entity"""
        snapshots = self.get_snapshots(entity_path)
        if not snapshots:
            return
            
        # Always keep the latest snapshot
        latest = snapshots[-1]
        is_active = self.is_election_active(datetime.now())
        
        for snapshot in snapshots[:-1]:  # Process all except latest
            if not self.should_retain_snapshot(snapshot, entity_type, is_active):
                logger.info(f"Removing old snapshot: {snapshot}")
                snapshot.unlink()

    def cleanup_year(self, year: str):
        """Clean up old snapshots for an entire election year"""
        year_path = self.data_path / year
        if not year_path.exists():
            return
            
        # Clean up national level
        self.cleanup_entity(year_path / 'nasjonalt' / 'norge', 'nasjonalt')
        
        # Clean up counties
        for fylke in (year_path / 'fylke').glob('fylke-*'):
            if fylke.is_dir():
                self.cleanup_entity(fylke, 'fylke')
        
        # Clean up municipalities
        for kommune in (year_path / 'kommune').glob('kommune-*'):
            if kommune.is_dir():
                self.cleanup_entity(kommune, 'kommune')
        
        # Clean up districts
        for krets in (year_path / 'kommune' / 'krets').glob('krets-*'):
            if krets.is_dir():
                self.cleanup_entity(krets, 'krets')

    def run(self):
        """Run cleanup for all election years"""
        logger.info("Starting data retention cleanup")
        
        for year_dir in self.data_path.glob('*'):
            if year_dir.is_dir() and year_dir.name.isdigit():
                logger.info(f"Processing year: {year_dir.name}")
                self.cleanup_year(year_dir.name)
        
        logger.info("Cleanup completed")

if __name__ == "__main__":
    # Load configuration from environment
    data_path = os.getenv('DATA_PATH', './data')
    
    manager = DataRetentionManager(data_path)
    manager.run()
