# Infrastructure

This directory contains infrastructure-as-code for BarnabeeNet:

- `hosts/` - Per-host configurations (battlestation, etc.)
- `modules/` - Reusable NixOS/Ansible modules
- `secrets/` - SOPS-encrypted secrets

## Secrets Management

Secrets are encrypted using SOPS with age. To decrypt:

```bash
sops -d secrets/secrets.yaml
```

Never commit decrypted secrets files.
