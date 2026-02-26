# Security Policy

## Sensitive Information Protection

### Configuration Files
**IMPORTANT**: The `config.yaml` file is now excluded from version control to protect sensitive information.

- **Never commit `config.yaml`** - This file may contain API keys, passwords, and other sensitive data
- **Use `config.yaml.template`** - This is the reference template that should be committed
- **Local configuration** - Copy `config.yaml.template` to `config.yaml` and add your secrets there

### API Keys and Credentials

When using this project:

1. **OpenAI API Keys**: Keep your `openai_api_key` value in `config.yaml` (which is gitignored)
2. **Web Passwords**: If using password protection, keep passwords in `config.yaml` only
3. **Environment Variables**: For production deployments, consider using environment variables instead of config files

### .gitignore Protection

The `.gitignore` file is configured to exclude:
- `config.yaml` - Main configuration with secrets
- `config.yaml.merged` - Temporary merged configs
- `recordings_metadata.json` - May contain user data
- `.env` and `.env.*` - Environment files
- `*.key`, `*.pem`, `*.secret` - Certificate and secret files
- `credentials.*` - Credential files

### Deployment Best Practices

When deploying to a Raspberry Pi:

1. **Never share SD card images** containing your `config.yaml` with API keys
2. **Use SSH keys** instead of password authentication
3. **Change default credentials** from `admin/password`
4. **Enable web password protection** in `config.yaml` (`web_password` setting)
5. **Keep firmware updated** - Regularly update Raspberry Pi OS and packages

### Reporting Security Issues

If you discover a security vulnerability, please:

1. **Do not open a public issue**
2. Email the repository owner directly
3. Include details about the vulnerability and potential impact
4. Allow reasonable time for a fix before public disclosure

## Git History Clean

As of the latest commit, this repository's git history has been verified to be clean of:
- OpenAI API keys
- Passwords
- Personal credentials
- Sensitive configuration data

All historical commits to `config.yaml` contained only empty API key fields (`openai_api_key: ""`).

## Checklist Before Pushing

Before pushing code or creating releases:

- [ ] No API keys in any committed files
- [ ] No passwords in configuration files
- [ ] No personal data in test files
- [ ] `.gitignore` properly excludes sensitive files
- [ ] `config.yaml.template` contains no secrets, only placeholders
- [ ] Documentation references template file, not actual config

## Additional Resources

- [OpenAI API Key Best Practices](https://platform.openai.com/docs/guides/safety-best-practices)
- [Raspberry Pi Security Guide](https://www.raspberrypi.com/documentation/computers/configuration.html#securing-your-raspberry-pi)
