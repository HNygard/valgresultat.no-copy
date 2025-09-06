# valgresultater.no-copy

A service to download and archive election results from valgresultat.no, tracking changes over time.

## Data Structure

The data is organized in a hierarchical structure by year and entity type:

```
data/
├── {YEAR}/                          # e.g., 2021, 2025, 2029
│   ├── nasjonalt/
│   │   ├── norge/
│   │   │   ├── {timestamp}.json     # Historical snapshots
│   │   │   └── ...
│   │   └── norge.json -> norge/{latest-timestamp}.json
│   ├── fylke/
│   │   ├── fylke-01/
│   │   │   ├── {timestamp}.json
│   │   │   └── ...
│   │   ├── fylke-01.json -> fylke-01/{latest-timestamp}.json
│   │   ├── fylke-02/
│   │   ├── fylke-02.json -> fylke-02/{latest-timestamp}.json
│   │   └── ... (fylke-03 through fylke-20)
│   ├── kommune/
│   │   ├── kommune-01-3001/
│   │   │   ├── {timestamp}.json
│   │   │   └── ...
│   │   ├── kommune-01-3001.json -> kommune-01-3001/{latest-timestamp}.json
│   │   ├── kommune-01-3002/
│   │   ├── kommune-01-3002.json -> kommune-01-3002/{latest-timestamp}.json
│   │   ├── krets/
│   │   │   ├── krets-01-3001-0001/
│   │   │   │   ├── {timestamp}.json
│   │   │   │   └── ...
│   │   │   ├── krets-01-3001-0001.json -> krets-01-3001-0001/{latest-timestamp}.json
│   │   │   └── ... (all voting districts)
│   │   └── ... (all municipalities)
│   └── config/
│       └── entities.json            # Master list of entities to monitor
```

### Key Features

- Each entity (national, county, municipality, district) maintains its own history
- Historical snapshots are stored with timestamps (YYYY-MM-DD__HHMM format)
- Symlinks provide easy access to latest data for each entity
- Changes are detected per-entity to minimize storage overhead

## Change Detection

Changes are detected during the download process by comparing content:

- Voting counts (`stemmer.total`, `stemmer.fhs`, etc.)
- Completion percentages (`opptalt` fields)
- Party results (`partier[].stemmer.resultat`)
- Other significant fields excluding metadata like `rapportGenerert`

New snapshots are only saved when changes are detected, with symlinks updated accordingly.

## Data Retention

The service includes automatic data retention management with different policies for election and non-election periods:

### Election Period (September-October)
- National level: 1 year retention
- County level: 6 months retention
- Municipality level: 3 months retention
- District level: 1 month retention

### Non-Election Period
- National level: Keep all data
- County level: Keep only latest snapshot
- Municipality level: Keep only latest snapshot
- District level: Keep only latest snapshot

The cleanup process runs daily at midnight to enforce these retention policies.

## Technical Implementation

### Docker Setup

```yaml
version: '3.8'
services:
  election-monitor:
    build: .
    environment:
      - API_BASE_URL=https://valgresultat.no/api
      - DATA_PATH=/data
      - ELECTION_YEARS=2021,2025,2029
      - POLL_INTERVAL_MINUTES=15
    volumes:
      - ./data:/data
    restart: unless-stopped
    
  cleanup:
    build: .
    command: ["python", "cleanup.py"]
    environment:
      - DATA_PATH=/data
    volumes:
      - ./data:/data
    labels:
      - "swarm.cronjob.enable=true"
      - "swarm.cronjob.schedule=0 0 * * *"  # Run daily at midnight
    
  web-interface:
    build: ./web
    ports:
      - "8080:80"  
    volumes:
      - ./data:/data:ro
    depends_on:
      - election-monitor
```

### Polling Schedule

Different entity types are polled at different frequencies during active election periods:

```python
ENTITY_SCHEDULES = {
    'nasjonalt': 300,      # Every 5 minutes
    'fylke': 600,          # Every 10 minutes  
    'kommune_major': 900,   # Every 15 minutes (pop > 50k)
    'kommune_minor': 1800,  # Every 30 minutes (pop < 50k)
    'krets': 3600          # Every hour
}
```

### API Endpoints

The service follows the valgresultat.no API structure:

```python
ENTITY_PATTERNS = {
    'nasjonalt': "/{year}/st",
    'fylke': "/{year}/st/{fylke_nr}",
    'kommune': "/{year}/st/{fylke_nr}/{kommune_nr}",
    'krets': "/{year}/st/{fylke_nr}/{kommune_nr}/{krets_nr}"
}
```

## Development

### Prerequisites

- Docker and Docker Compose
- Python 3.8+
- Access to valgresultat.no API

### Getting Started

1. Clone the repository
2. Configure environment variables
3. Run with Docker Compose:
   ```bash
   docker-compose up -d
   ```

### Monitoring

The service includes basic monitoring of:
- Download success/failure rates
- API response times
- Storage usage
- Change detection statistics
- Data retention status
