#!/usr/bin/env python3
"""
US Airport Taxiway NAIP Image Collector
=======================================
Collects FREE public domain aerial imagery from USDA NAIP.

Usage:
    python collect.py -n 10          # Test with 10 airports
"""

import argparse
import csv
import json
import time
from datetime import datetime
from pathlib import Path
from urllib.request import urlretrieve

import requests

# =============================================================================
# CONFIGURATION - UPDATE THIS IF NEEDED
# =============================================================================
EARTH_ENGINE_PROJECT = "us-airports-aerial-images"  # Your GCP project ID

IMAGE_SIZE_METERS = 300   # Each image covers 300m x 300m (~1m per pixel)
IMAGE_PIXELS = 360        # Output resolution: 360x360 (standard for ML models)
DOWNLOAD_DELAY = 0.3      # Seconds between downloads

# =============================================================================
# INITIALIZE EARTH ENGINE
# =============================================================================
print("Connecting to Google Earth Engine...")
try:
    import ee
    ee.Initialize(project=EARTH_ENGINE_PROJECT)
    print(f"✓ Connected to Earth Engine (project: {EARTH_ENGINE_PROJECT})\n")
except Exception as e:
    print(f"✗ Error: {e}")
    print("\nTroubleshooting:")
    print("  1. Run: earthengine set_project us-airports-aerial-images")
    print("  2. Run: earthengine authenticate --force")
    exit(1)


# =============================================================================
# AIRPORT LOADER
# =============================================================================
def load_us_airports(cache_dir: Path, limit: int) -> list:
    """Download and load US airports from OurAirports (public domain)"""
    
    cache_dir.mkdir(parents=True, exist_ok=True)
    airports_file = cache_dir / "airports.csv"
    runways_file = cache_dir / "runways.csv"
    
    # Download data files if not cached
    if not airports_file.exists():
        print("Downloading airport database...")
        r = requests.get("https://davidmegginson.github.io/ourairports-data/airports.csv", timeout=60)
        airports_file.write_text(r.text, encoding='utf-8')
        
    if not runways_file.exists():
        r = requests.get("https://davidmegginson.github.io/ourairports-data/runways.csv", timeout=60)
        runways_file.write_text(r.text, encoding='utf-8')
    
    # Load runway lengths
    runway_lengths = {}
    with open(runways_file, 'r', encoding='utf-8') as f:
        for row in csv.DictReader(f):
            icao = row.get('airport_ident', '')
            try:
                length = float(row.get('length_ft', 0))
                runway_lengths[icao] = max(runway_lengths.get(icao, 0), length)
            except:
                pass
    
    # Load and filter airports
    airports = []
    with open(airports_file, 'r', encoding='utf-8') as f:
        for row in csv.DictReader(f):
            # US only
            if row.get('iso_country') != 'US':
                continue
            
            # Large, medium, small airports only
            apt_type = row.get('type', '')
            if apt_type not in ['large_airport', 'medium_airport', 'small_airport']:
                continue
            
            icao = row.get('ident', '')
            if not icao:
                continue
            
            # Minimum runway length 3000 ft
            if runway_lengths.get(icao, 0) < 3000:
                continue
            
            # Valid coordinates
            try:
                lat = float(row.get('latitude_deg', 0))
                lon = float(row.get('longitude_deg', 0))
                if lat == 0 and lon == 0:
                    continue
            except:
                continue
            
            airports.append({
                'icao': icao,
                'iata': row.get('iata_code', ''),
                'name': row.get('name', ''),
                'lat': lat,
                'lon': lon,
                'type': apt_type,
                'state': row.get('iso_region', '').replace('US-', ''),
            })
    
    # Sort by airport size (large first)
    type_order = {'large_airport': 0, 'medium_airport': 1, 'small_airport': 2}
    airports.sort(key=lambda a: (type_order.get(a['type'], 9), a['name']))
    
    # Limit results
    airports = airports[:limit]
    
    # Summary
    large = sum(1 for a in airports if a['type'] == 'large_airport')
    medium = sum(1 for a in airports if a['type'] == 'medium_airport')
    small = sum(1 for a in airports if a['type'] == 'small_airport')
    print(f"✓ Loaded {len(airports)} US airports (Large: {large}, Medium: {medium}, Small: {small})\n")
    
    return airports


# =============================================================================
# NAIP IMAGE DOWNLOADER
# =============================================================================
def download_naip_image(lat: float, lon: float, filepath: Path) -> bool:
    """Download a single NAIP image from Earth Engine"""
    
    if filepath.exists():
        return True  # Already downloaded
    
    try:
        # Create region around point
        point = ee.Geometry.Point([lon, lat])
        region = point.buffer(IMAGE_SIZE_METERS / 2).bounds()
        
        # Get most recent NAIP image for this location
        naip = (ee.ImageCollection('USDA/NAIP/DOQQ')
                .filterBounds(point)
                .sort('system:time_start', False)  # Most recent first
                .first()
                .select(['R', 'G', 'B']))  # RGB bands only
        
        # Get download URL
        url = naip.getThumbURL({
            'region': region,
            'dimensions': IMAGE_PIXELS,
            'format': 'png',
        })
        
        # Download image
        urlretrieve(url, filepath)
        
        # Verify file size (small files are usually errors)
        if filepath.stat().st_size < 5000:
            filepath.unlink()
            return False
        
        return True
        
    except Exception as e:
        # Silently fail - no NAIP coverage or other error
        return False


def get_grid_positions(center_lat: float, center_lon: float, num_images: int) -> list:
    """Calculate grid positions around airport center"""
    
    positions = [(center_lat, center_lon)]  # Always include center
    
    if num_images >= 5:
        # Offset ~280 meters (some overlap between images)
        offset = IMAGE_SIZE_METERS * 0.7 / 111000  # Convert to degrees
        positions += [
            (center_lat + offset, center_lon),      # North
            (center_lat - offset, center_lon),      # South
            (center_lat, center_lon + offset),      # East
            (center_lat, center_lon - offset),      # West
        ]
    
    if num_images >= 9:
        positions += [
            (center_lat + offset, center_lon + offset),   # NE
            (center_lat + offset, center_lon - offset),   # NW
            (center_lat - offset, center_lon + offset),   # SE
            (center_lat - offset, center_lon - offset),   # SW
        ]
    
    return positions[:num_images]


# =============================================================================
# MAIN COLLECTION FUNCTION
# =============================================================================
def collect_dataset(num_airports: int, images_per_airport: int, output_dir: Path):
    """Main collection orchestrator"""
    
    # Setup directories
    images_dir = output_dir / "images"
    metadata_dir = output_dir / "metadata"
    cache_dir = output_dir / "cache"
    
    images_dir.mkdir(parents=True, exist_ok=True)
    metadata_dir.mkdir(parents=True, exist_ok=True)
    
    # Print header
    print("=" * 60)
    print("   NAIP AIRPORT TAXIWAY IMAGE COLLECTOR")
    print("   Source: USDA NAIP (Public Domain - FREE)")
    print("=" * 60 + "\n")
    
    # Load airports
    airports = load_us_airports(cache_dir, num_airports)
    
    # Estimate time
    total_images = len(airports) * images_per_airport
    est_minutes = total_images * (DOWNLOAD_DELAY + 0.3) / 60
    print(f"Plan: {len(airports)} airports × {images_per_airport} images = {total_images} images")
    print(f"Estimated time: {est_minutes:.1f} minutes\n")
    print("-" * 60)
    
    # Collection stats
    successful_airports = 0
    total_downloaded = 0
    collection_log = []
    
    # Collect images for each airport
    for idx, airport in enumerate(airports, 1):
        icao = airport['icao']
        name = airport['name'][:32].ljust(32)
        state = airport['state']
        
        print(f"[{idx:3d}/{len(airports)}] {icao} {name} ({state})", end=" ", flush=True)
        
        # Get positions for this airport
        positions = get_grid_positions(airport['lat'], airport['lon'], images_per_airport)
        
        downloaded = 0
        for img_idx, (lat, lon) in enumerate(positions):
            filename = f"{icao}_{img_idx:02d}.png"
            filepath = images_dir / filename
            
            if download_naip_image(lat, lon, filepath):
                downloaded += 1
                collection_log.append({
                    'icao': icao,
                    'iata': airport['iata'],
                    'name': airport['name'],
                    'state': state,
                    'type': airport['type'],
                    'airport_lat': airport['lat'],
                    'airport_lon': airport['lon'],
                    'image_lat': lat,
                    'image_lon': lon,
                    'filename': filename,
                    'file_size': filepath.stat().st_size,
                    'source': 'NAIP',
                    'timestamp': datetime.now().isoformat(),
                })
            
            time.sleep(DOWNLOAD_DELAY)
        
        if downloaded > 0:
            successful_airports += 1
            total_downloaded += downloaded
            print(f"✓ {downloaded} images")
        else:
            print("✗ No NAIP coverage")
    
    print("-" * 60)
    
    # Save metadata
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    
    # Save collection log as CSV
    if collection_log:
        log_file = metadata_dir / f"collection_log_{timestamp}.csv"
        with open(log_file, 'w', newline='', encoding='utf-8') as f:
            writer = csv.DictWriter(f, fieldnames=collection_log[0].keys())
            writer.writeheader()
            writer.writerows(collection_log)
        print(f"\n✓ Saved log: {log_file}")
    
    # Save stats as JSON
    stats = {
        'project': EARTH_ENGINE_PROJECT,
        'source': 'USDA NAIP',
        'license': 'Public Domain',
        'total_airports': len(airports),
        'successful_airports': successful_airports,
        'total_images': total_downloaded,
        'image_size_meters': IMAGE_SIZE_METERS,
        'image_pixels': f"{IMAGE_PIXELS}x{IMAGE_PIXELS}",
        'resolution': f"~{IMAGE_SIZE_METERS/IMAGE_PIXELS:.2f}m per pixel",
        'timestamp': timestamp,
    }
    stats_file = metadata_dir / f"stats_{timestamp}.json"
    with open(stats_file, 'w') as f:
        json.dump(stats, f, indent=2)
    print(f"✓ Saved stats: {stats_file}")
    
    # Print summary
    print("\n" + "=" * 60)
    print("   COLLECTION COMPLETE")
    print("=" * 60)
    print(f"   📁 Output: {output_dir.absolute()}")
    print(f"   🛫 Airports: {successful_airports}/{len(airports)} with NAIP coverage")
    print(f"   🖼️  Images: {total_downloaded}")
    print(f"   📄 License: Public Domain (free to use & publish)")
    print("=" * 60 + "\n")
    
    return stats


# =============================================================================
# COMMAND LINE INTERFACE
# =============================================================================
def main():
    parser = argparse.ArgumentParser(
        description="Collect NAIP aerial imagery of US airport taxiways",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
    python collect.py -n 10              # Quick test (10 airports)
    python collect.py -n 100 -i 5        # Medium dataset (500 images)
    python collect.py -n 200 -i 9        # Large dataset (1800 images)

Output Structure:
    dataset/
    ├── images/           # PNG images (ICAO_00.png, ICAO_01.png, ...)
    ├── metadata/         # CSV log and JSON stats
    └── cache/            # Downloaded airport database
        """
    )
    
    parser.add_argument(
        '-n', '--num-airports',
        type=int,
        default=10,
        help='Number of airports to collect (default: 10)'
    )
    parser.add_argument(
        '-i', '--images-per-airport',
        type=int,
        default=9,
        choices=[1, 5, 9],
        help='Images per airport: 1=center, 5=cross, 9=grid (default: 9)'
    )
    parser.add_argument(
        '-o', '--output',
        type=Path,
        default=Path('./dataset'),
        help='Output directory (default: ./dataset)'
    )
    
    args = parser.parse_args()
    
    try:
        collect_dataset(
            num_airports=args.num_airports,
            images_per_airport=args.images_per_airport,
            output_dir=args.output,
        )
    except KeyboardInterrupt:
        print("\n\n⚠️  Interrupted by user. Partial data saved.\n")
        return 1
    except Exception as e:
        print(f"\n❌ Error: {e}\n")
        return 1
    
    return 0


if __name__ == "__main__":
    exit(main())
