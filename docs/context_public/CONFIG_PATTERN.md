# Configuration File Pattern

## Philosophy

All deployment-specific configuration files are centralized in the `/config` directory at the repository root. This provides:

- **Single source of truth** for all deployment settings
- **Easy discovery** - operators know exactly where to look
- **Simple management** - all configs in one flat directory
- **Clear separation** - tracked templates vs gitignored deployment files

## Directory Structure

```
config/
├── switches.conf.example    # Template (tracked in git)
└── switches.conf            # Deployment-specific (gitignored)
```

## Pattern

For each service that needs deployment-specific configuration:

1. **Template file** - `.example` suffix, tracked in git, shows format and examples
2. **Deployment file** - Real config with production values, gitignored for security/flexibility
3. **Docker volume mount** - Maps from `./config/filename` to container path
4. **Documentation** - Service README explains config format and options

## Migration Status

This is an ongoing pattern we're establishing across the stack:

- ✅ **netgear-backup** - `switches.conf` moved from `services/netgear-backup/` to `config/`
- 🔄 **telegraf** - `device-overrides.json` currently in `telegraf/conf.d/` (legacy location)
- ⏳ **Future services** - All new services should follow this pattern

## Guidelines

- **Flat structure** - Use `config/filename.conf`, not `config/service-name/filename.conf`
- **Descriptive names** - File name should indicate purpose (e.g., `switches.conf` not `netgear.conf`)
- **Always gitignore** - Deployment-specific files must be in `.gitignore`
- **Always provide template** - Include `.example` file with comments explaining format
- **Document in service README** - Link to config files and explain their purpose

## Example: switches.conf

The netgear-backup service uses `config/switches.conf` to define which switches to back up:

```conf
# Format: IP  NAME  MODEL
192.168.105.249  FOH.103.249  M4300
```

- Template: `config/switches.conf.example` (tracked)
- Deployment: `config/switches.conf` (gitignored)
- Docker mount: `./config/switches.conf:/config/switches.conf:ro`
- Service reads from: `/config/switches.conf` inside container

## Benefits

- **Deployment flexibility** - Same code, different configs per environment
- **Security** - Production IPs/credentials never committed to git
- **Operator efficiency** - All configs in predictable location
- **Clean service directories** - Services contain code, not deployment state
- **Version control** - Templates tracked, deployment files ignored
