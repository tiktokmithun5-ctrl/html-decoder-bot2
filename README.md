# HTML Decoder Telegram Bot

## Features
- Receives `.html`, `.htm`, `.js`, `.txt`, `.json` documents in Telegram.
- Safely decodes HTML entities, common JavaScript `\\uXXXX` / `\\xXX` escapes, and whole-file Base64 HTML.
- Includes a decoder for the specific emoji/symbol substitution cipher format used in the sample HTML.
- Never runs the uploaded HTML or JavaScript.

## Run locally
1. Create a bot with `@BotFather` and copy its token.
2. Install Python 3.10+.
3. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```
4. Set your token:
   - Linux/macOS: `export BOT_TOKEN="YOUR_TOKEN"`
   - Windows PowerShell: `$env:BOT_TOKEN="YOUR_TOKEN"`
5. Run:
   ```bash
   python bot.py
   ```

## Deploy with Docker
```bash
docker build -t html-decoder-bot .
docker run --rm -e BOT_TOKEN="YOUR_TOKEN" html-decoder-bot
```

Keep your bot token private. Decoding is best-effort: proprietary or unknown obfuscation may require a matching algorithm.
