# Copilot Agent Capabilities Reference

## Available Tools

### Execution
| Tool | Use For |
|------|---------|
| `runInTerminal` | Shell commands (bash, ssh, make) |
| `runTask` | VS Code tasks from tasks.json |
| `runTests` | Pytest with coverage |

### File Operations
| Tool | Use For |
|------|---------|
| `createFile` | New files |
| `editFiles` | Modify existing files |
| `readFile` | View file contents |

### Search
| Tool | Use For |
|------|---------|
| `codebase` | Semantic code search |
| `textSearch` | Grep-style search |
| `fileSearch` | Find files by name |

### External
| Tool | Use For |
|------|---------|
| `web` | Search documentation |
| `fetch` | Get web page content |
| `githubRepo` | Search GitHub repos |

## Quick Architecture Reference

### Key Files
- **Agent prompts:** `src/barnabeenet/prompts/*.txt` (edit directly, no UI)
- **Model config:** `config/llm.yaml` (agents section)
- **Dashboard:** `src/barnabeenet/static/` (HTML/JS/CSS)
- **API routes:** `src/barnabeenet/api/routes/`

### Dashboard Pages
Dashboard, Chat, Memory, Logic, Self-Improve, Logs, Family, Entities, Config

### Common Tasks
- **Change agent behavior:** Edit `prompts/{agent}_agent.txt`
- **Change model:** Edit `config/llm.yaml` → `agents.{agent}.model`
- **Add dashboard page:** HTML div + nav link + JS init + CSS
- **Add API endpoint:** Route file + register in `main.py` + tests

## Multi-Machine Commands

### Run on VM
```bash
ssh thom@192.168.86.51 'command'
```

### Multi-line on VM
```bash
ssh thom@192.168.86.51 << 'EOF'
cd ~/barnabeenet
command1
command2
EOF
```

### Copy files to VM
```bash
scp localfile thom@192.168.86.51:~/barnabeenet/
```

### Copy files from VM
```bash
scp thom@192.168.86.51:~/barnabeenet/file ./
```