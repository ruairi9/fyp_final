# SDOS Dashboard

Web-based monitoring dashboard for the SDOS K3s cluster.

## Structure
```
sdos-dashboard/
├── app.py              # Main dashboard application
├── templates/          # HTML templates (for future pages)
├── static/             # CSS, JS, images (for future assets)
├── Dockerfile          # Docker containerization
├── docker-compose.yml  # Docker Compose config
└── README.md           # This file
```

## Running

### Direct Python
```bash
cd ~/fyp-cluster/sdos-dashboard
python3 app.py
```

### With Docker
```bash
cd ~/fyp-cluster/sdos-dashboard
docker-compose up -d
```

## Features
- Real-time K3s cluster monitoring
- Jenkins pipeline status
- CPU, Memory, Disk usage graphs
- Server health status
- Auto-refresh every 5 seconds

## Adding New Pages
Place new page files in `templates/` directory and update routes in `app.py`.
