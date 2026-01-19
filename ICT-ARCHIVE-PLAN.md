# ICT Archive Plan

## Overview
Mirror the entire ICT wiki and file archive from quagmyre.com as a personal backup and potentially host your own wiki.

## Source URLs
- **Files:** https://files.quagmyre.com/files/ICTStudies/
- **Wiki:** https://info.quagmyre.com/xwiki/bin/view/Forex/The-Inner-Circle-Trader/

## Content Available

### ICT-Spaces (Twitter Spaces & Soundcloud)
- **2022-2025** audio recordings (AAC, M4A, MP3)
- **SRT transcripts** with timestamps
- **DOCX** documents
- Organized by year: `/ICT-Spaces/2022/`, `/2023/`, etc.

### Other Content
- `/ICT-Twitter/` - Tweet archives (HTML by month)
- `/ICT-Telegram/` - Telegram content
- `/ICT-Rumble/` - Rumble videos
- `/ICT-Notes/` - Study materials
- `/Historical/` - Archived content

## Estimated Size
- **Without YouTube videos:** ~30-50 GB
- **Storage available:** 4TB Windows PC

---

## Download Instructions (Windows)

### Option 1: HTTrack (Recommended - GUI)
1. Download HTTrack: https://www.httrack.com/
2. Install and open
3. Create new project named "ICT-Archive"
4. Set destination: `D:\ICT-Archive` (or preferred drive)
5. Add URLs:
   ```
   https://files.quagmyre.com/files/ICTStudies/
   https://info.quagmyre.com/xwiki/bin/view/Forex/The-Inner-Circle-Trader/
   ```
6. Start and let it run overnight

### Option 2: wget (Command Line)
```powershell
# Install wget
winget install GnuWin32.Wget

# Create folder
mkdir D:\ICT-Archive
cd D:\ICT-Archive

# Download all files
wget -r -np -c -N --reject "index.html*" https://files.quagmyre.com/files/ICTStudies/

# Download wiki pages
wget -r -np -c -N https://info.quagmyre.com/xwiki/bin/view/Forex/The-Inner-Circle-Trader/
```

### Option 3: Specific Content Only (Spaces + Transcripts)
```powershell
# Just the Twitter Spaces audio and transcripts (~20GB)
wget -r -np -c -N https://files.quagmyre.com/files/ICTStudies/ICT-Spaces/
```

---

## Host Your Own Wiki

### Platform Options

| Platform | Difficulty | Cost | Notes |
|----------|------------|------|-------|
| Wiki.js | Easy | Free | Modern, Node.js based |
| BookStack | Easy | Free | Documentation-focused |
| XWiki | Medium | Free | Same as source wiki |
| Notion | Easiest | Free tier | No self-hosting needed |
| GitBook | Easy | Free | Good for docs |

### Free Hosting: Oracle Cloud

1. **Sign up:** https://cloud.oracle.com/free
2. **Create VM:** Always Free tier (24GB RAM, 4 OCPU)
3. **Install Wiki.js:**
   ```bash
   # On the VM
   curl -sSL https://wiki.js.org/install.sh | bash
   ```
4. **Import content** from your downloaded archive
5. **Point domain** to VM's public IP

### Alternative: Cloudflare Pages (Static)
- Convert wiki to static HTML
- Host free on Cloudflare Pages
- No server management needed

---

## Future: Video Content Pipeline

Once archive is downloaded, use SRT transcripts to:

1. **Match quotes to timestamps**
   - Parse SRT files
   - Fuzzy match EdgeOfICT quotes
   - Extract start/end times

2. **Cut audio clips**
   ```bash
   ffmpeg -i audio.m4a -ss 00:15:32 -to 00:15:45 -c copy clip.m4a
   ```

3. **Generate videos**
   - Quote card image as background
   - ICT's voice as audio
   - Export as vertical video (1080x1920)

4. **Post to TikTok/Shorts/Reels**

---

## Checklist

- [ ] Download HTTrack or install wget
- [ ] Run archive download overnight
- [ ] Verify download completeness
- [ ] Sign up for Oracle Cloud Free Tier
- [ ] Set up Wiki.js
- [ ] Import content to wiki
- [ ] Build quote-to-audio matcher (separate branch)
- [ ] Create video generation pipeline

---

## Notes
- Source wiki is maintained by quagmyre.com community
- Archive for personal backup/study purposes
- SRT files are key for the video content pipeline
