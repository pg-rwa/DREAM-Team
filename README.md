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

## Project Structure

```
DREAM-Team/
├── dream.py                 # Entry point
├── pyproject.toml           # Package config
├── dream_team/
│   ├── __init__.py
│   ├── cli.py               # Interactive CLI (the single interface)
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
│   └── ui/
│       └── dashboard.py     # Terminal dashboard UI
```

## License

MIT
