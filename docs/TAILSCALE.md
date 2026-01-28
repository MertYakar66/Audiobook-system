# Tailscale Remote Access Guide

Access your audiobook library from anywhere using Tailscale's secure mesh VPN.

## Why Tailscale?

- **Zero configuration**: No port forwarding needed
- **Secure**: All traffic encrypted, no exposure to internet
- **Easy**: Works through NAT, firewalls, and cellular
- **Free**: Free tier supports 100 devices

## Setup Overview

```
[Your PC] <--Tailscale VPN--> [Your Phone]
    |                              |
Audiobookshelf              Mobile App (Plappa/ABS)
  :13378
```

## Step 1: Install Tailscale on Your PC

1. Download from [tailscale.com/download](https://tailscale.com/download)
2. Install and sign in with Google/Microsoft/GitHub
3. Your PC gets a Tailscale IP (e.g., `100.x.y.z`)

**Find your Tailscale IP:**
```cmd
tailscale ip
```

## Step 2: Install Tailscale on Phone

1. Download Tailscale from App Store / Play Store
2. Sign in with same account
3. Enable VPN when prompted

## Step 3: Configure Audiobookshelf Access

Your Audiobookshelf is now accessible via Tailscale IP:

```
http://100.x.y.z:13378
```

Replace `100.x.y.z` with your actual Tailscale IP.

### Test Connection

From your phone (with Tailscale connected):
1. Open browser
2. Navigate to `http://100.x.y.z:13378`
3. Log in to Audiobookshelf

## Step 4: Set Up Mobile App

### Option A: Audiobookshelf App (Android)

1. Install from Play Store
2. Server URL: `http://100.x.y.z:13378`
3. Login with your credentials

### Option B: Plappa (iOS)

1. Install from App Store
2. Add server: `http://100.x.y.z:13378`
3. Login with your credentials

### Option C: Any Podcast App (Generic)

Audiobookshelf can serve books as podcast feeds:
1. In Audiobookshelf, get RSS feed URL for a book
2. Add to your podcast app
3. Stream like a podcast

## Advanced: MagicDNS

Tailscale's MagicDNS gives you a friendly hostname.

1. Enable MagicDNS in Tailscale admin console
2. Access via: `http://your-pc-name:13378`

## Advanced: Always-On Access

To keep your PC accessible:

### Windows Power Settings
1. Settings > System > Power
2. Disable sleep when plugged in
3. Or use "Away Mode" for media serving

### Tailscale Settings
1. Open Tailscale
2. Enable "Run on startup"
3. Enable "Run unattended"

## Advanced: Subnet Router (Optional)

If you want to access other services on your home network:

1. On your PC, enable subnet routing:
   ```cmd
   tailscale up --advertise-routes=192.168.1.0/24
   ```
2. Approve in Tailscale admin console
3. Access any device on your home network via Tailscale

## Security Best Practices

1. **Use strong Audiobookshelf password**
2. **Enable Tailscale key expiry** (Admin Console)
3. **Review connected devices** regularly
4. **Don't share your Tailscale account**

## Troubleshooting

### Can't connect from phone

1. Ensure Tailscale is connected on both devices
2. Check both devices are on same Tailnet (account)
3. Try: `tailscale ping your-pc-name`

### Connection slow

1. Check if using relay (DERP) vs direct
   ```cmd
   tailscale status
   ```
2. Direct connections are faster
3. Same network? Try local IP instead

### Audiobookshelf not responding

1. Ensure Docker is running
2. Check container status:
   ```cmd
   docker ps
   ```
3. Restart if needed:
   ```cmd
   cd docker && docker-compose restart
   ```

### Progress not syncing

1. Check internet connection on phone
2. Force sync in app settings
3. Verify server URL is correct

## Mobile Data Usage

Audiobooks are large files. To minimize data:

1. **Download books** when on WiFi
2. Use **lower quality** streams if available
3. Enable **smart downloads** in app

Typical audiobook sizes:
- 10 hour book at 64kbps: ~280 MB
- 10 hour book at 128kbps: ~560 MB

## Quick Reference

| What | Where |
|------|-------|
| Tailscale IP | Run `tailscale ip` |
| Audiobookshelf URL | `http://<tailscale-ip>:13378` |
| MagicDNS URL | `http://<pc-name>:13378` |

## Alternatives to Tailscale

If Tailscale doesn't work for you:

1. **ZeroTier**: Similar mesh VPN
2. **WireGuard**: Manual VPN setup
3. **Cloudflare Tunnel**: Web-only access
4. **Port Forwarding**: Not recommended (security risk)

Tailscale is recommended for its simplicity and security.
