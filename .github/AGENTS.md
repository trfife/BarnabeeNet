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