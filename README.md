# DREAM Team - AI Agent Team Manager

> **D**ynamic **R**esponsive **E**ngineering **A**gent **M**anager

An AI-powered team management system where a CTO agent oversees specialized project agents, all powered by Claude Code. You provide high-level direction, the CTO breaks it down, and project agents execute.

## Architecture

```
┌─────────────────────────────────────────────────┐
│                  YOU (Founder)                    │
│          Ideas, feedback, direction               │
└──────────────────────┬──────────────────────────┘
                       │
                       ▼
┌─────────────────────────────────────────────────┐
│              CTO Agent (AI)                      │
│  Analyzes requests, creates plans, delegates     │
└──────┬──────────┬──────────┬────────────────────┘
       │          │          │
       ▼          ▼          ▼
┌──────────┐ ┌──────────┐ ┌──────────┐
│ Agent:   │ │ Agent:   │ │ Agent:   │
│ Fitness  │ │ MINE     │ │ Bitcoin  │
│ App      │ │ Project  │ │ Bot      │
└──────────┘ └──────────┘ └──────────┘
  Each agent has its own Claude Code session
  and works within its project repository
```

## Quick Start

### Prerequisites

- Python 3.10+
- [Claude Code CLI](https://docs.anthropic.com/en/docs/claude-code) installed and authenticated
- Git configured with GitHub access

### Installation

```bash
# Clone this repo
git clone https://github.com/pg-rwa/DREAM-Team.git
cd DREAM-Team

# Install the package
pip install -e .

# Or run directly
python dream.py
```

### First Run

```bash
# Launch the DREAM Team dashboard
dream
# or
python dream.py
```

You'll see the DREAM Team dashboard with the ASCII art logo and command reference.

## Usage

### Adding Projects

```bash
# Add a project from GitHub
DREAM> add https://github.com/username/fitness-app --name fitness-app --desc "My fitness tracking application"

# Add with tech stack info
DREAM> add https://github.com/username/bitcoin-bot --name bitcoin-bot --stack python,tensorflow --desc "Bitcoin price prediction bot"

# Add the MINE project
DREAM> add https://github.com/username/MINE --name MINE --desc "MINE project"
```

### Talking to the CTO

The CTO is your main interface. Just type naturally:

```bash
# Give direction
DREAM> talk I want to add a social features to the fitness app - friend challenges and leaderboards

# Ask for status
DREAM> talk What's the status across all projects?

# Prioritize work
DREAM> talk Focus on the bitcoin bot this week, I want to improve prediction accuracy

# Start a new project idea
DREAM> talk I have an idea for a new project - a personal finance dashboard that aggregates all my accounts
```

Anything you type that isn't a command is automatically sent to the CTO.

### Direct Agent Commands

```bash
# Get project status
DREAM> status fitness-app

# Have an agent review its codebase
DREAM> review bitcoin-bot

# Assign a specific task
DREAM> work MINE Add unit tests for the core module

# View all tasks
DREAM> tasks
```

### Other Commands

```bash
# View dashboard
DREAM> dashboard

# Configure settings
DREAM> config github_username your-username
DREAM> config team_name "My DREAM Team"

# Remove a project
DREAM> remove old-project

# Exit
DREAM> quit
```

## How It Works

1. **You speak to the CTO** with high-level ideas and feedback
2. **CTO analyzes** your request and creates a delegation plan
3. **CTO assigns tasks** to the appropriate project agents
4. **Project agents execute** using Claude Code within their repos
5. **Results flow back** through the CTO to you

Each project agent:
- Has its own Claude Code session
- Works within its cloned repository
- Understands its project's tech stack and patterns
- Can read, write, and modify code
- Reports progress and blockers

## Configuration

Config is stored at `~/.dream-team/config.json`:

```json
{
  "github_username": "your-username",
  "workspace_dir": "~/.dream-team/projects",
  "cto_name": "CTO",
  "team_name": "DREAM Team",
  "projects": [...]
}
```

Project repos are cloned to `~/.dream-team/projects/`.

## Web Dashboard (Server Mode)

Access DREAM Team from any device via a web browser.

### Local

```bash
# Start the web server
dream-server
# or
python -m dream_team.web.run

# First run prints your API key
# Open http://localhost:8000 and enter the key
```

### Deploy to DigitalOcean

**Option A: Quick setup on a $12/mo droplet (2GB RAM, Ubuntu 22.04)**

```bash
# SSH into your droplet
ssh root@your-droplet-ip

# Clone and run setup
git clone https://github.com/pg-rwa/DREAM-Team.git /opt/dream-team
cd /opt/dream-team
chmod +x deploy/setup.sh
./deploy/setup.sh

# Set your Anthropic API key
echo 'Environment=ANTHROPIC_API_KEY=sk-ant-...' >> /etc/systemd/system/dream-team.service
systemctl daemon-reload
systemctl start dream-team

# Get your login key
python3 -m dream_team.web.run --show-key
```

**Option B: Docker**

```bash
# Set your API key
export ANTHROPIC_API_KEY=sk-ant-...

# Build and run
docker compose up -d

# Get your login key
docker compose exec dream-team python3 -m dream_team.web.run --show-key
```

**Add HTTPS (recommended):**

```bash
apt install caddy
# Edit /etc/caddy/Caddyfile:
#   dream.yourdomain.com { reverse_proxy localhost:8000 }
systemctl restart caddy
```

### Web API

All endpoints require authentication (Bearer token or session cookie).

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/auth/login` | Login with API key |
| GET | `/api/team/status` | Full team status |
| POST | `/api/cto/talk` | Talk to the CTO |
| GET | `/api/projects` | List projects |
| POST | `/api/projects` | Add project |
| GET | `/api/projects/{name}/status` | Project status |
| GET | `/api/tasks` | List tasks |
| POST | `/api/tasks` | Create task |
| POST | `/api/tasks/{id}/execute` | Execute task |
| WS | `/ws` | Real-time updates |

## Project Structure

```
DREAM-Team/
├── dream.py                 # CLI entry point
├── pyproject.toml           # Package config
├── Dockerfile               # Container build
├── docker-compose.yml       # Docker orchestration
├── deploy/
│   ├── setup.sh             # DO droplet setup script
│   ├── dream-team.service   # systemd service file
│   └── Caddyfile            # HTTPS reverse proxy config
├── dream_team/
│   ├── __init__.py
│   ├── cli.py               # Interactive CLI
│   ├── team.py              # Team orchestrator
│   ├── agents/
│   │   ├── base.py          # Base agent with Claude Code execution
│   │   ├── cto.py           # CTO agent (delegation & planning)
│   │   └── project_agent.py # Project-specific agents
│   ├── config/
│   │   └── settings.py      # Configuration management
│   ├── github/
│   │   └── integration.py   # GitHub repo operations
│   ├── tasks/
│   │   └── manager.py       # Task tracking & queue
│   ├── ui/
│   │   └── dashboard.py     # Terminal dashboard UI
│   └── web/
│       ├── server.py         # FastAPI app + API endpoints
│       ├── auth.py           # API key + session auth
│       ├── workers.py        # Background task processor
│       ├── run.py            # Web server launcher
│       └── templates/
│           ├── login.html    # Login page
│           └── dashboard.html # Web dashboard
```

## License

MIT
