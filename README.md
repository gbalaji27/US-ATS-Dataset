# US-ATS: US Airport Taxiway Segmentation Dataset

[![License: CC BY 4.0](https://img.shields.io/badge/License-CC%20BY%204.0-lightgrey.svg)](https://creativecommons.org/licenses/by/4.0/)
[![Python 3.8+](https://img.shields.io/badge/python-3.8+-blue.svg)](https://www.python.org/downloads/)

A semantic segmentation dataset for airport ground infrastructure from high-resolution aerial imagery.

## 📋 Overview

US-ATS (US Airport Taxiway Segmentation) is a dataset for semantic segmentation of airport ground infrastructure. Images are collected from US airports using **USDA NAIP satellite imagery** (Public Domain - FREE) via Google Earth Engine.

### Key Features

- **High Resolution**: ~0.83 meters per pixel
- **5 Semantic Classes**: Background, Taxiway, Runway, Apron, Taxilane
- **Public Domain Source**: USDA NAIP imagery (free to use & publish)
- **Reproducible**: Full code to collect images from any US airport

## 🗂️ Repository Structure

```
US-ATS-Dataset/
├── data/
│   └── images/               # Sample images
├── scripts/
│   ├── collect.py            # Image collection script
│   └── dataset/              # Output from collection
│       ├── images/           # Collected images
│       ├── metadata/         # CSV log and JSON stats
│       └── cache/            # Airport database cache
├── docs/
│   └── CLASS_DEFINITIONS.md
├── README.md
├── LICENSE
└── requirements.txt
```

## 📥 Dataset Access

### Sample Images
This repository includes sample images in `data/images/`.

### Full Dataset
Contact: gbalaji2705@gmail.com

## 🚀 Quick Start

### Installation

```bash
git clone https://github.com/gbalaji27/US-ATS-Dataset.git
cd US-ATS-Dataset
pip install -r requirements.txt
```

### Setup Google Earth Engine

```bash
# Set your GCP project
earthengine set_project us-airports-aerial-images

# Authenticate (one-time)
earthengine authenticate
```

## 🔧 Collect Your Own Data

### Basic Usage

```bash
cd scripts

# Quick test (10 airports, 9 images each = 90 images)
python collect.py -n 10

# Medium dataset (100 airports = ~500 images)
python collect.py -n 100 -i 5

# Large dataset for thesis (200 airports = ~1800 images)
python collect.py -n 200 -i 9
```

### Command Line Options

| Option | Description | Default |
|--------|-------------|---------|
| `-n, --num-airports` | Number of airports to collect | 10 |
| `-i, --images-per-airport` | Images per airport (1, 5, or 9) | 9 |
| `-o, --output` | Output directory | ./dataset |

### Output Structure

```
dataset/
├── images/           # PNG images (ICAO_00.png, ICAO_01.png, ...)
├── metadata/         # CSV log and JSON stats
└── cache/            # Downloaded airport database
```

### How It Works

1. **Downloads US airport database** from OurAirports (public domain)
2. **Filters airports**: US only, runway ≥3000ft, large/medium/small types
3. **Downloads NAIP imagery** via Google Earth Engine
4. **Saves metadata**: CSV log with coordinates, JSON stats

## 🎨 Class Definitions

| ID | Class | Description |
|----|-------|-------------|
| 0 | Background | Grass, buildings, water, vehicles |
| 1 | Taxiway | Paths connecting runways to terminals |
| 2 | Runway | Takeoff and landing strips |
| 3 | Apron | Aircraft parking areas |
| 4 | Taxilane | Paths within apron areas |

## 📊 Image Specifications

| Property | Value |
|----------|-------|
| Size | 360 × 360 pixels |
| Coverage | 300 × 300 meters |
| Resolution | ~0.83 m/pixel |
| Format | PNG (8-bit RGB) |
| Source | USDA NAIP |
| License | **Public Domain** |

## 📝 Citation

```bibtex
@article{gowrammagari2024usats,
  title={US-ATS: US Airport Taxiway Segmentation Dataset},
  author={Gowrammagari, Balaji},
  journal={IEEE Data Descriptions},
  year={2024}
}
```

## 📜 License

- **Code**: MIT License
- **Dataset**: CC BY 4.0
- **Source Imagery**: Public Domain (USDA NAIP)

## 🙏 Acknowledgements

- Dr. Chad Mourning - Advisor, Ohio University
- USDA - NAIP imagery (Public Domain)
- Google - Earth Engine platform
- OurAirports - Airport database

## 📧 Contact

- **Author**: Balaji Gowrammagari
- **Email**: gbalaji2705@gmail.com
- **Institution**: Ohio University, School of EECS